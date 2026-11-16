#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supervisor Event Listener + WebSocket 广播 (含指令控制版 + 抖动循环检测 + 手动确认)
- 监听所有进程状态变化，实时推送给前端网页
- 响应前端发来的启停/重启/日志拉取/确认抖动指令
- 每 10 秒节点全局校准一次，解决重启瞬间丢事件、状态卡 STOPPING 的问题
- 抖动循环检测：2 分钟内抖动 ≥ 3 次标记为抖动，稳定 2 分钟后自动解除
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
import traceback

# ---------- 日志（输出到 stderr，避免污染 stdout 的事件协议） ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("listener")

# ---------- websockets 配置 ----------
WS_CLIENTS = set()
WS_HOST    = "0.0.0.0"
WS_PORT    = 8765

# ---------- RPC 配置 ----------
HTTP_PORT = 8000    # supervisor 配置的端口
USER      = "admin" # supervisor 配置的用户
PASSWD    = "admin" # supervisor 配置的密码
SUPERVISOR_RPC_URL = f"http://{USER}:{PASSWD}@localhost:{HTTP_PORT}/RPC2"

# ---------- 进程抖动检测 配置 ----------
CRASH_WINDOW_SECONDS = 60 # 时间窗口，秒
CRASH_THRESHOLD      = 3        # 时间窗口内抖动次数达到该值，进程状态标记为抖动
CALIBRATION_INTERVAL = 10  #节点校准时间间隔，秒

# ---------- 检测到进程抖动处理方式 配置 ----------
KEEP_FLAP_MARK = True # 是否保持抖动标记（True 不自动清除标记，手动确认处理后再清除标记）
AUTO_STOPPED = True # 是否允许抖动进程自动停止, True 自动停止

# ---------- 本监听器的变量 配置 ----------
MAIN_LOOP = None
CRASH_STATE_LOCK = threading.Lock()
RESTART_TIMESTAMPS = defaultdict(list) # { full_name: [最近启动的时间戳列表] }
ACKNOWLEDGED_CRASHES = {} # { full_name: 被管理员手动确认过的时间戳 }
EVER_RUNNING = set() # 曾经成功进入过 RUNNING 的进程集合，用于区分「起不来」和「能起来但反复挂」


################ 监听程序主体 ################

def detect_crash_loop(full_name):
    """
    滑动窗口检测：
    - 记录该进程每次进入 STARTING 的时间戳
    - 时间戳条数如果达到阈值 CRASH_THRESHOLD 并且抖动未被确认处理，is_flapping=True
    - KEEP_FLAP_MARK=False 清理超出窗口时间 CRASH_WINDOW_SECONDS 的旧时间戳
    - 如果被管理员确认过，且确认后未出现新的抖动，则返回 is_flapping=False
    返回 (is_flapping, count, last_start, acknowledged)
    """
    now = time.time()
    with CRASH_STATE_LOCK:
        timestamps = RESTART_TIMESTAMPS[full_name]
        
        #如果不保持抖动标记，则不断清除窗口时间以外的记录，这样抖动记数会一直减少
        #达不到抖动阈值时，抖动标记就会清除
        if not KEEP_FLAP_MARK:
            
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
    
    仅当满足「真·频繁抖动」语义时才计数：
    1. 该进程**曾经成功进入过 RUNNING**（即真正跑起来过）
       —— 从未跑起来、反复 BACKOFF/FATAL 的进程不归抖动，归入「异常进程」
    2. 这次 STARTING 是**从 EXITED 自动拉起**（运行中异常退出，被 Supervisor 拉起来）
       —— 从 STOPPED 启动属于管理员手动操作，不计数
       —— 从 BACKOFF 启动属于启动失败重试，进程根本没跑起来，不计抖动（归异常进程）
    返回是否真正计了一次抖动。
    """
    with CRASH_STATE_LOCK:
        # 条件1：从未进入 RUNNING → 根本没跑起来过，属于启动失败（异常进程），不计抖动
        if full_name not in EVER_RUNNING:
            return False
        # 条件2：从 STOPPED 启动 → 管理员手动 start/restart，不计抖动
        if from_state == "STOPPED":
            return False
        # 条件3：从 BACKOFF 启动 → 启动失败重试，进程没跑起来，属于异常进程，不计抖动
        if from_state == "BACKOFF":
            return False
        # 条件4：从 EXITED（运行中异常退出）→ 真·抖动重启，计数
        if from_state == "EXITED":
            RESTART_TIMESTAMPS[full_name].append(time.time())
            return True
        # 其他 from_state 不计数
        return False


def mark_running(full_name):
    """进程成功进入 RUNNING 时调用：标记该进程「能跑起来」，并清理窗口外旧抖动记录。"""
    now = time.time()
    with CRASH_STATE_LOCK:
        EVER_RUNNING.add(full_name)
        # 清理 CRASH_WINDOW_SECONDS 秒以前的旧抖动记录，稳定运行后标记会自动消失
        cutoff = now - CRASH_WINDOW_SECONDS
        timestamps = RESTART_TIMESTAMPS[full_name]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)


def acknowledge_crash(full_name):
    """管理员手动确认已处理该抖动，立即清除警告"""
    with CRASH_STATE_LOCK:
        ACKNOWLEDGED_CRASHES[full_name] = time.time()
        # 同时清空该进程的重启记录，这样即使再次抖动也会重新计数
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
    
    def _retry(self, func, *args, **kwargs):
        """RPC 失败时自动重连一次"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"RPC 调用失败，尝试重连: {e}")
            self._connect()
            return func(*args, **kwargs)
    
    def get_all_processes(self):
        """获取所有进程完整信息
        在原始数据中，追加了抖动循环检测数据
        """
        try:
            procs = self._retry(self.rpc.supervisor.getAllProcessInfo)
            result = []
            for p in procs:
                full_name = f"{p['group']}:{p['name']}" if p["group"] != p["name"] else p["name"]
                # 当前处于 RUNNING 的进程标记为「能跑起来」，
                # 这样即使 listener 自身重启，也能在下次全量校准时重建 EVER_RUNNING
                if p["statename"] == "RUNNING":
                    mark_running(full_name)#标记进程进入 RUNNING 状态
                is_flapping, flap_count, last_start, acknowledged = detect_crash_loop(full_name)
                result.append({
                    "name": p["name"],
                    "group": p["group"],
                    "full_name": full_name,
                    "start": p["start"],
                    "stop": p["stop"],
                    "state": p["state"], #状态数字编号
                    "statename": p["statename"], #状态名称
                    "pid": p["pid"],
                    "description": p.get("description", ""),
                    "exitstatus": p.get("exitstatus", 0),
                    "flapping": is_flapping,
                    "flap_count": flap_count,
                    "last_restart_ts": last_start,
                    "acknowledged": acknowledged,
                    "sync_interval": CALIBRATION_INTERVAL, #此监听器的同步间隔，秒
                })
            return result
        except Exception as e:
            logger.error(f"getAllProcessInfo 失败: {e}")
            return []
    
    def start_process(self, full_name):
        """启动进程，full_name 形如 'group:name' 或 'name'"""
        try:
            self._retry(self.rpc.supervisor.startProcess, full_name, True)
            return {"success": True}
        except Fault as e:
            return {"success": False, "error": e.faultString}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def stop_process(self, full_name):
        """停止进程"""
        try:
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
    
    def startAll(self):
        """启动全部进程"""
        try:
            self._retry(self.rpc.supervisor.startAllProcesses)
            return {"success": True}
        except Fault as e:
            return {"success": False, "error": e.faultString}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def stopAll(self):
        """停止全部进程
        但是会把本监听器也给停止了，所以此方法前端已经删掉了
        """
        try:
            self._retry(self.rpc.supervisor.stopAllProcesses)
            return {"success": True}
        except Fault as e:
            return {"success": False, "error": e.faultString}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def reloadConfig(self):
        """重新加载配置
        相当于 supervisorctl reread && supervisorctl update
        """
        try:
            added, changed, removed = self._retry(self.rpc.supervisor.reloadConfig)[0]
            
            if not added and not changed and not removed:
                logger.info("ℹ️ 配置文件无变化")
                return
            else:
                logger.info(f"📋 检测到配置有变化 → 新增:{added if added else '无'} | 修改:{changed if changed else '无'} | 删除:{removed if removed else '无'}")
            
            # ========== 1. 处理删除的进程：必须先停，再移除 ==========
            for group in removed:
                try:
                    logger.info(f"⏳ 正在停止删除进程: {group}")
                    self._retry(self.rpc.supervisor.stopProcessGroup, group, True) # True，等进程完全退出再往下走
                    self._retry(self.rpc.supervisor.removeProcessGroup, group)
                    logger.info(f"🗑️ 已停止并删除: {group}")
                except Fault as e:
                    # 直接打印supervisor返回的具体错误，比如STILL_RUNNING/NO_PROCESS
                    logger.error(f"❌ 删除{group}失败，错误码:{e.faultCode}，原因:{e.faultString}")
                except Exception as e:
                    logger.error(f"❌ 删除{group}异常: {str(e)}")
            
            # ========== 2. 处理修改的进程：先停旧的→移除旧配置→加新配置自动启动 ==========
            for group in changed:
                try:
                    logger.info(f"⏳ 正在重载修改进程: {group}")
                    self._retry(self.rpc.supervisor.stopProcessGroup, group, True)
                    self._retry(self.rpc.supervisor.removeProcessGroup, group)
                    self._retry(self.rpc.supervisor.addProcessGroup, group)  # add会自动按新配置启动进程
                    logger.info(f"🔄 已重载修改: {group}")
                except Fault as e:
                    logger.error(f"❌ 重载{group}失败，错误码:{e.faultCode}，原因:{e.faultString}")
                except Exception as e:
                    logger.error(f"❌ 重载{group}异常: {str(e)}")
            
            # ========== 3. 处理新增的进程：直接add自动启动 ==========
            for group in added:
                try:
                    self._retry(self.rpc.supervisor.addProcessGroup, group)
                    logger.info(f"✅ 已启动新增: {group}")
                except Fault as e:
                    logger.error(f"❌ 启动{group}失败，错误码:{e.faultCode}，原因:{e.faultString}")
                except Exception as e:
                    logger.error(f"❌ 启动{group}异常: {str(e)}")
            
            logger.info("🎉 配置应用完成")
            return True
        
        except Exception as e:
            logger.error(f"❌ 连接supervisor失败: {str(e)}")
            traceback.print_exc()
            return False


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
            
            # ---------- 操作单个进程指令：启动/停止/重启 ----------
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
            
            # ---------- 操作全部进程指令：启动全部/停止全部 ----------
            # 但是会把本监听器也给停止了，所以此方法前端已经删掉了
            elif msg_type == "commandAll":
                action = msg.get("action")
                req_id = msg.get("req_id")
                if not action:
                    continue
                logger.info(f"收到指令: {action}")
                
                if action == "startAll":
                    result = await asyncio.to_thread(sup.startAll)
                elif action == "stopAll":
                    result = await asyncio.to_thread(sup.stopAll)
                
                await websocket.send(json.dumps({
                    "type": "command_result",
                    "req_id": req_id,
                    "result": result,
                }, ensure_ascii=False))
            
            # ---------- 手动确认抖动已处理 ----------
            elif msg_type == "acknowledge_flap":
                proc = msg.get("process")
                req_id = msg.get("req_id")
                if proc:
                    logger.info(f"前端确认已处理抖动: {proc}")
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
            
            # ---------- 手动刷新当前节点（包括重新加载配置） ----------
            elif msg_type == "refresh":
                req_id = msg.get("req_id")
                logger.info(f"前端请求手动刷新当前节点")
                
                # 重新加载当前节点的配置文件
                await asyncio.to_thread(sup.reloadConfig)
                
                # 只给当前请求的节点发送全量数据
                all_procs = await asyncio.to_thread(sup.get_all_processes)
                await websocket.send(json.dumps({
                    "type": "full_sync",
                    "data": all_procs,
                    "ts": time.time(),
                }, ensure_ascii=False))
                await websocket.send(json.dumps({
                    "type": "op_result",
                    "req_id": req_id,
                    "success": True,
                    "message": "刷新完成"
                }, ensure_ascii=False))
            
            # ---------- 重启整个 Supervisor ----------
            elif msg_type == "restart_supervisor":
                req_id = msg.get("req_id")
                logger.warning("前端请求重启Supervisor守护进程！")
                try:
                    await websocket.send(json.dumps({
                        "type": "op_result",
                        "req_id": req_id,
                        "success": True,
                        "message": "重启指令已发送"
                    }, ensure_ascii=False))
                    
                    # 调用Supervisor RPC重启主进程，注意rpc对象是sup.rpc
                    await asyncio.to_thread(sup.rpc.supervisor.restart())
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
            "ts": time.time(), #全量同步时间戳
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
        
        # 抖动循环检测（精确版）：
        #   进入 RUNNING   → 标记该进程「能跑起来」，清理窗口外旧记录
        #   进入 STARTING  → 满足以下两个条件才计一次抖动：
        #       1) 该进程曾成功进入过 RUNNING（根本没起来的 FATAL/BACKOFF 不算）
        #       2) 从 EXITED 启动（运行中异常退出，被 Supervisor 自动拉起）
        #       → 从 STOPPED 启动（管理员手动 start/restart）不计入
        #       → 从 BACKOFF 启动（启动失败重试，进程没跑起来）不计入
        from_state = body_data.get("from_state", "")
        if eventname == "PROCESS_STATE_RUNNING":
            mark_running(full_name)#标记进程进入 RUNNING 状态
        elif eventname == "PROCESS_STATE_STARTING":
            record_restart(full_name, from_state=from_state)#记录进程 重启 计数
        
        is_flapping, flap_count, last_start, acknowledged = detect_crash_loop(full_name)
        
        # 新增逻辑，发生抖动，并且此进程不在集合中，就停止此进程，由人工处理
        # 判断进程当前状态，如果已经停止了，就不再重复停止
        if AUTO_STOPPED and is_flapping and eventname not in ("PROCESS_STATE_STOPPED", "PROCESS_STATE_EXITED"):
            sup.stop_process(full_name)
        
        
        event = {
            "type": "state_change",
            "event": eventname,
            "process": full_name,
            "raw_process": proc_name,
            "group": group_name,
            "from_state": body_data.get("from_state", ""),
            "pid": body_data.get("pid", ""),
            "expected": body_data.get("expected", ""),
            "ts": time.time(), #事件时间戳
            "flapping": is_flapping,
            "flap_count": flap_count,
            "last_restart_ts": last_start,
            "acknowledged": acknowledged,
        }
        
        if is_flapping and eventname == "PROCESS_STATE_RUNNING":
            logger.warning(
                f"⚠️ 进程 {full_name} 频繁抖动！{CRASH_WINDOW_SECONDS}秒内已抖动 {flap_count} 次"
            )
        
        logger.info(f"事件: {eventname} | {full_name}{' [FLAPPING]' if is_flapping else ''}{' [ACK]' if acknowledged else ''}")
        push_event(event)
        
        write_stdout("RESULT 2\nOK")
        write_stdout("READY\n")
        

if __name__ == "__main__":
    main()
