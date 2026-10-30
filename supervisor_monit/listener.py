#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supervisor Event Listener + WebSocket 广播 (含指令控制版 + 崩溃循环检测 + 手动确认)
- 监听所有进程状态变化，实时推送给前端网页
- 响应前端发来的启停/重启/日志拉取/确认崩溃指令
- 每 10 秒全量校准一次，解决重启瞬间丢事件、状态卡 STOPPING 的问题
- 崩溃循环检测：5 分钟内重启 ≥ 3 次标记为异常，稳定 5 分钟后自动解除
- 管理员可手动点「确认已处理」立即清除警告

适配 websockets >= 12（新版 handler 只接收一个 websocket 参数）
"""
import sys
import json
import time
import asyncio
import threading
import logging
from collections import defaultdict
from xmlrpc.client import ServerProxy, Fault

import websockets

# ---------- 日志（输出到 stderr，避免污染 stdout 的事件协议） ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("listener")

# ---------- 全局配置 ----------
WS_CLIENTS = set()
WS_HOST = "0.0.0.0"
WS_PORT = 8765

# ★ 你的 XML-RPC 地址（带用户名密码），按需修改
SUPERVISOR_RPC_URL = "http://admin:admin@localhost:8000/RPC2"

# 崩溃循环检测阈值
CRASH_WINDOW_SECONDS = 300 # 时间窗口，秒
CRASH_THRESHOLD = 3        # 时间窗口内重启次数达到该值标记为崩溃
CALIBRATION_INTERVAL = 30  #校准时间间隔，秒

MAIN_LOOP = None
CRASH_STATE_LOCK = threading.Lock()

# { full_name: [最近启动的时间戳列表] }
RESTART_TIMESTAMPS = defaultdict(list)

# { full_name: 被管理员手动确认过的时间戳 }
ACKNOWLEDGED_CRASHES = {}

# 曾经成功进入过 RUNNING 的进程集合，用于区分「起不来」和「能起来但反复挂」
EVER_RUNNING = set()


def detect_crash_loop(full_name):
    """
    滑动窗口检测：
    - 记录该进程每次进入 STARTING 的时间戳
    - 清理超出窗口的旧记录
    - 如果被管理员确认过，且确认后未出现新的崩溃，则返回 flapping=False
    返回 (is_flapping, count, last_start_ts, acknowledged)
    """
    now = time.time()
    with CRASH_STATE_LOCK:
        timestamps = RESTART_TIMESTAMPS[full_name]
        # 清理窗口外的记录
        cutoff = now - CRASH_WINDOW_SECONDS
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        count = len(timestamps)
        last_start = timestamps[-1] if timestamps else 0

        # 检查是否被手动确认过
        ack_ts = ACKNOWLEDGED_CRASHES.get(full_name, 0)
        # 如果最后一次重启发生在确认之后，说明确认后又崩了，确认失效
        acknowledged = ack_ts > 0 and last_start <= ack_ts

        is_flapping = count >= CRASH_THRESHOLD and not acknowledged
        return is_flapping, count, last_start, acknowledged


def record_restart(full_name, from_state=None):
    """
    进程进入 STARTING 时调用，记录一次启动时间戳。
    
    仅当满足「真·频繁崩溃」语义时才计数：
    1. 该进程**曾经成功进入过 RUNNING**（即真正跑起来过）
       —— 从未跑起来、反复 BACKOFF/FATAL 的进程不归崩溃，归入「异常进程」
    2. 这次 STARTING 是**从 EXITED 自动拉起**（运行中异常退出，被 Supervisor 拉起来）
       —— 从 STOPPED 启动属于管理员手动操作，不计数
       —— 从 BACKOFF 启动属于启动失败重试，进程根本没跑起来，不计崩溃（归异常进程）
    返回是否真正计了一次崩溃。
    """
    with CRASH_STATE_LOCK:
        # 条件1：从未进入 RUNNING → 根本没跑起来过，属于启动失败（异常进程），不计崩溃
        if full_name not in EVER_RUNNING:
            return False
        # 条件2：从 STOPPED 启动 → 管理员手动 start/restart，不计崩溃
        if from_state == "STOPPED":
            return False
        # 条件3：从 BACKOFF 启动 → 启动失败重试，进程没跑起来，属于异常进程，不计崩溃
        if from_state == "BACKOFF":
            return False
        # 条件4：从 EXITED（运行中异常退出）→ 真·崩溃重启，计数
        if from_state == "EXITED":
            RESTART_TIMESTAMPS[full_name].append(time.time())
            return True
        # 其他 from_state 不计数
        return False


def mark_running(full_name):
    """进程成功进入 RUNNING 时调用：标记该进程「能跑起来」，并清理窗口外旧崩溃记录。"""
    now = time.time()
    with CRASH_STATE_LOCK:
        EVER_RUNNING.add(full_name)
        # 清理 CRASH_WINDOW_SECONDS 秒以前的旧崩溃记录，稳定运行后标记会自动消失
        cutoff = now - CRASH_WINDOW_SECONDS
        timestamps = RESTART_TIMESTAMPS[full_name]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)


def acknowledge_crash(full_name):
    """管理员手动确认已处理该崩溃，立即清除警告"""
    with CRASH_STATE_LOCK:
        ACKNOWLEDGED_CRASHES[full_name] = time.time()
        # 同时清空该进程的重启记录，这样即使再次崩溃也会重新计数
        RESTART_TIMESTAMPS[full_name].clear()
    return {"success": True, "message": "已确认处理"}


# ================= 1. Supervisor XML-RPC 操作封装 =================
class SupervisorProxy:
    def __init__(self, url):
        self.url = url
        self.rpc = None
        self._connect()

    def _connect(self):
        self.rpc = ServerProxy(self.url)

    def _retry_name(self, func_name, *args):
        """RPC 失败时自动重连一次；func_name 为 supervisor.xxx 方法名"""
        try:
            return getattr(self.rpc.supervisor, func_name)(*args)
        except Exception as e:
            logger.warning(f"RPC 调用失败，尝试重连: {e}")
            self._connect()
            return getattr(self.rpc.supervisor, func_name)(*args)

    def _retry(self, func, *args, **kwargs):
        """RPC 失败时自动重连一次"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"RPC 调用失败，尝试重连: {e}")
            self._connect()
            return func(*args, **kwargs)

    def get_all_processes(self):
        """获取所有进程完整信息（含崩溃循环检测结果）"""
        try:
            # procs = self._retry_name("getAllProcessInfo")
            procs = self._retry(self.rpc.supervisor.getAllProcessInfo)
            result = []
            for p in procs:
                full_name = f"{p['group']}:{p['name']}" if p["group"] != p["name"] else p["name"]
                # 当前处于 RUNNING 的进程标记为「能跑起来」，
                # 这样即使 listener 自身重启，也能在下次全量校准时重建 EVER_RUNNING
                if p["statename"] == "RUNNING":
                    mark_running(full_name)#标记进程进入 RUNNING 状态
                is_flapping, crash_count, last_start, acknowledged = detect_crash_loop(full_name)
                result.append({
                    "name": p["name"],
                    "group": p["group"],
                    "full_name": full_name,
                    "start": p["start"],
                    "stop": p["stop"],
                    "state": p["state"],
                    "statename": p["statename"],
                    "pid": p["pid"],
                    "description": p.get("description", ""),
                    "exitstatus": p.get("exitstatus", 0),
                    "flapping": is_flapping,
                    "crash_count": crash_count,
                    "last_restart_ts": last_start,
                    "acknowledged": acknowledged,
                })
            return result
        except Exception as e:
            logger.error(f"getAllProcessInfo 失败: {e}")
            return []

    def start_process(self, full_name):
        """启动进程，full_name 形如 'group:name' 或 'name'"""
        try:
            # self._retry_name("startProcess", full_name, True)
            self._retry(self.rpc.supervisor.startProcess, full_name, True)
            return {"success": True}
        except Fault as e:
            return {"success": False, "error": e.faultString}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_process(self, full_name):
        """停止进程"""
        try:
            # self._retry_name("stopProcess", full_name, True)
            self._retry(self.rpc.supervisor.stopProcess, full_name, True)
            return {"success": True}
        except Fault as e:
            return {"success": False, "error": e.faultString}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restart_process(self, full_name):
        """重启进程"""
        stop_res = self.stop_process(full_name)
        if not stop_res["success"]:
            # 如果进程本来就是停的，stop 会报错，不影响直接 start
            if "NOT_RUNNING" not in stop_res.get("error", ""):
                return stop_res
        time.sleep(0.5)
        return self.start_process(full_name)
    

sup = SupervisorProxy(SUPERVISOR_RPC_URL)


# ================= 2. WebSocket 服务 =================
async def ws_handler(websocket):
    """处理前端 WebSocket 连接（收 + 发）。websockets>=12 只传一个参数"""
    WS_CLIENTS.add(websocket)
    logger.info(f"前端已连接，当前连接数: {len(WS_CLIENTS)}")

    # 新连接一建立，立刻发全量快照
    try:
        all_procs = await asyncio.to_thread(sup.get_all_processes)
        await websocket.send(json.dumps({
            "type": "full_sync",
            "data": all_procs,
            "ts": time.time(),
        }, ensure_ascii=False))
    except Exception as e:
        logger.error(f"全量同步失败: {e}")

    try:
        async for raw_msg in websocket:
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            # ---------- 操作单进程指令：启动/停止/重启 ----------
            if msg_type == "command":
                action = msg.get("action")
                proc   = msg.get("process")
                req_id = msg.get("req_id")
                if not action or not proc:
                    continue
                logger.info(f"收到指令: {action} {proc}")

                # 在后台线程执行RPC，不阻塞事件循环
                if action == "start":
                    result = await asyncio.to_thread(sup.start_process, proc)
                elif action == "stop":
                    result = await asyncio.to_thread(sup.stop_process, proc)
                elif action == "restart":
                    result = await asyncio.to_thread(sup.restart_process, proc)
                else:
                    result = {"success": False, "error": f"未知操作: {action}"}

                await websocket.send(json.dumps({
                    "type": "command_result",
                    "req_id": req_id,
                    "process": proc,
                    "result": result,
                }, ensure_ascii=False))

            # ---------- 手动确认崩溃已处理 ----------
            elif msg_type == "acknowledge_flap":
                proc = msg.get("process")
                req_id = msg.get("req_id")
                if proc:
                    logger.info(f"管理员确认已处理崩溃: {proc}")
                    result = await asyncio.to_thread(acknowledge_crash, proc)
                    # 先回复结果
                    await websocket.send(json.dumps({
                        "type": "command_result",
                        "req_id": req_id,
                        "process": proc,
                        "result": result,
                    }, ensure_ascii=False))
                    # 然后立即全量广播一次状态给所有前端（让警告消失）
                    all_procs = await asyncio.to_thread(sup.get_all_processes)
                    await broadcast(json.dumps({
                        "type": "full_sync",
                        "data": all_procs,
                        "ts": time.time(),
                    }, ensure_ascii=False))
            
            # ---------- 重启整个 Supervisor ----------
            elif msg_type == "restart_supervisor":
                req_id = msg.get("req_id")
                logger.warning("管理员请求重启Supervisor守护进程！")
                try:
                    await websocket.send(json.dumps({
                        "type": "op_result",
                        "req_id": req_id,
                        "success": True,
                        "message": "重启指令已发送"
                    }, ensure_ascii=False))
                    # 重启Supervisor主进程
                    def do_restart():
                        # 调用Supervisor RPC重启主进程，注意rpc对象是sup.rpc
                        sup.rpc.supervisor.restart()
                    await asyncio.to_thread(do_restart)
                except Exception as e:
                    logger.error(f"重启Supervisor失败: {e}")
                    await websocket.send(json.dumps({
                        "type": "op_result",
                        "req_id": req_id,
                        "success": False,
                        "message": str(e)
                    }, ensure_ascii=False))

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        logger.error(f"WS 连接异常: {e}")
    finally:
        WS_CLIENTS.discard(websocket)
        logger.info(f"前端断开，当前连接数: {len(WS_CLIENTS)}")


async def broadcast(message: str):
    """向所有前端广播"""
    if not WS_CLIENTS:
        return
    dead = set()
    for ws in WS_CLIENTS:
        try:
            await ws.send(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        WS_CLIENTS.discard(ws)


def push_event(event: dict):
    """线程安全地投递事件到 asyncio 主循环"""
    if MAIN_LOOP is None:
        logger.warning("MAIN_LOOP 未就绪，事件被丢弃: %s", event.get("type"))
        return
    msg = json.dumps(event, ensure_ascii=False)
    try:
        asyncio.run_coroutine_threadsafe(broadcast(msg), MAIN_LOOP)
    except RuntimeError as e:
        logger.warning(f"事件投递失败: {e}")


def run_ws_server():
    """在独立线程里跑 WebSocket 服务"""
    global MAIN_LOOP
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    MAIN_LOOP = loop

    async def _serve():
        async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
            logger.info(f"WebSocket 服务已启动: ws://{WS_HOST}:{WS_PORT}")
            await asyncio.Future()

    loop.run_until_complete(_serve())


# ================= 3. 后台校准线程 =================
def calibration_daemon():
    """每 CALIBRATION_INTERVAL 秒全量广播一次真实状态，兜底校准纠偏"""
    while True:
        time.sleep(CALIBRATION_INTERVAL)
        all_procs = sup.get_all_processes()
        push_event({
            "type": "full_sync",
            "data": all_procs,
            "ts": time.time(),
        })


# ================= 4. Supervisor 事件协议处理 =================
def write_stdout(s: str):
    sys.stdout.write(s)
    sys.stdout.flush()


def read_stdin_line() -> str:
    return sys.stdin.readline()


def parse_event_header(line: str) -> dict:
    header = {}
    for kv in line.strip().split(" "):
        if ":" in kv:
            k, v = kv.split(":", 1)
            header[k] = v
    return header


def parse_event_body(body: str) -> dict:
    data = {}
    for kv in body.strip().split(" "):
        if ":" in kv:
            k, v = kv.split(":", 1)
            data[k] = v
    return data


def main():
    ws_thread = threading.Thread(target=run_ws_server, daemon=True)
    ws_thread.start()

    for _ in range(50):
        if MAIN_LOOP is not None:
            break
        time.sleep(0.1)

    threading.Thread(target=calibration_daemon, daemon=True).start()

    logger.info("Event Listener 准备就绪，等待 Supervisor 事件...")
    write_stdout("READY\n")

    while True:
        line = read_stdin_line()
        if not line:
            logger.info("stdin 已关闭，监听器退出")
            break
        
        '''
        以下就是事件监听器的功能实现，当进程发生变化时，通知前端。
        所有 PROCESS_STATE_* 事件都有的 3 个基础字段 processname groupname from_state
        除了默认的键值对集合以外，有时还会额外的加入 pid 键, 代表了启动进程的UNIX进程ID
        
        注意：pid 不只是现在运行状态的，也有可能代表已退出进程的，所以才有了前端替换 pid 的函数
        
        举例说明如下：
        PROCESS_STATE_RUNNING, 从 STARTING 转到 RUNNING, 此时的 pid 是现在正常运行的
        processname:cat groupname:cat from_state:STARTING pid:2766
        
        PROCESS_STATE_STOPPING, 从 RUNNING 或 STARTING 状态 转到 STOPPING 状态, 此时的 pid 是前一个状态的
        processname:cat groupname:cat from_state:STARTING pid:2766
        
        PROCESS_STATE_STOPPED, 从 STOPPING 转到 STOPPED, 此时的 pid 就是已退出进程的
        processname:cat groupname:cat from_state:STOPPING pid:2766
        
        PROCESS_STATE_BACKOFF, tries 表示在过渡到 RUNNING 或 FATAL 之前，此进程进入该状态的次数（tries 的值不会大于进程的“startretries”参数），当次数达到 startretries 时，就会进入 FATAL 状态
        processname:cat groupname:cat from_state:STOPPED tries:1
        
        PROCESS_STATE_EXITED, expected 代表进程是否以预期的退出码退出。如果退出码非预期，则为0，如果退出码符合预期，则为1
        processname:cat groupname:cat from_state:RUNNING expected:0 pid:2766
        
        事件的变化，过渡状态
        
        STARTING -> RUNNING -> STOPPING -> STOPPED -> STARTING
        
        STARTING -> STOPPING -> STOPPED
        
        STARTING -> BACKOFF -> FATAL
        
        RUNNING -> EXITED
        
        '''
        
        header = parse_event_header(line)
        eventname = header.get("eventname", "UNKNOWN")
        try:
            payload_len = int(header.get("len", "0"))
        except ValueError:
            payload_len = 0
        
        body = sys.stdin.read(payload_len) if payload_len > 0 else ""
        body_data = parse_event_body(body)
        
        proc_name = body_data.get("processname", "unknown")#进程名，不含组名
        group_name = body_data.get("groupname", "")#组名
        
        #亲测验证：当进程名与组名重名时，可以直接使用进程名，
        #此时组名对此进程依然有效，继续支持使用组名:进程名进行操作，
        #也继续支持对此组名进行操作，命令也会影响到此进程
        full_name = f"{group_name}:{proc_name}" if group_name and group_name != proc_name else proc_name
        
        # 崩溃循环检测（精确版）：
        #   进入 RUNNING   → 标记该进程「能跑起来」，清理窗口外旧记录
        #   进入 STARTING  → 满足以下两个条件才计一次崩溃：
        #       1) 该进程曾成功进入过 RUNNING（根本没起来的 FATAL/BACKOFF 不算）
        #       2) 从 EXITED 启动（运行中异常退出，被 Supervisor 自动拉起）
        #       → 从 STOPPED 启动（管理员手动 start/restart）不计入
        #       → 从 BACKOFF 启动（启动失败重试，进程没跑起来）不计入
        from_state = body_data.get("from_state", "")
        if eventname == "PROCESS_STATE_RUNNING":
            mark_running(full_name)#标记进程进入 RUNNING 状态
        elif eventname == "PROCESS_STATE_STARTING":
            record_restart(full_name, from_state=from_state)#记录进程 重启 计数
        
        is_flapping, crash_count, last_start, acknowledged = detect_crash_loop(full_name)
        
        event = {
            "type": "state_change",
            "event": eventname,
            "process": full_name,
            "raw_process": proc_name,
            "group": group_name,
            "from_state": body_data.get("from_state", ""),
            "pid": body_data.get("pid", ""),
            "expected": body_data.get("expected", ""),
            "ts": time.time(),
            "flapping": is_flapping,
            "crash_count": crash_count,
            "last_restart_ts": last_start,
            "acknowledged": acknowledged,
        }
        
        if is_flapping and eventname == "PROCESS_STATE_RUNNING":
            logger.warning(
                f"⚠️ 进程 {full_name} 频繁重启！{CRASH_WINDOW_SECONDS}秒内已重启 {crash_count} 次"
            )
        
        logger.info(f"事件: {eventname} | {full_name}{' [FLAPPING]' if is_flapping else ''}{' [ACK]' if acknowledged else ''}")
        push_event(event)
        
        write_stdout("RESULT 2\nOK")
        write_stdout("READY\n")
        

if __name__ == "__main__":
    main()
