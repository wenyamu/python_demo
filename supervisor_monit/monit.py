from flask import Flask, render_template, url_for, request, jsonify, redirect, Response
from xmlrpc.client import ServerProxy, Transport, SafeTransport

import os
from collections import Counter
import json
import time

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import traceback

from threading import Lock

from datetime import datetime

TZ="Asia/Shanghai"
fmt="%Y-%m-%d %H:%M:%S.%3f"

def now_str(fmt):
    """ 用datetime实现时间格式化，彻底抛弃time.strftime，支持%f/%3f"""
    now = datetime.now()
    # 先处理毫秒占位符%3f（要在%f之前替换，避免冲突）
    if "%3f" in fmt:
        ms = f"{now.microsecond // 1000:03d}"
        fmt = fmt.replace("%3f", ms)
    return now.strftime(fmt)


# 全局线程池，不用每次创建销毁，max_workers根据你服务器数量调，比如监控20台就设20
RPC_EXECUTOR = ThreadPoolExecutor(max_workers=20, thread_name_prefix="server_rpc")

app = Flask(__name__,
            template_folder='/python/supervisor_monit/templates',
            static_folder='/python/supervisor_monit/asset',
            static_url_path="/",
            )

'''
# __name__ 本文件的文件名（不含后缀）

# template_folder 存放模板的目录，缺省值为当前项目目录下的templates目录

# static_folder 存放静态文件的目录，缺省值为当前项目目录下的 static 目录

# static_url_path 访问静态文件的路由设置，配合 static_folder 使用

一句话区分
‌static_folder = 磁盘上的物理位置‌：服务器上那个‌真实存在‌的文件夹路径（文件到底躺在哪）。
‌static_url_path = 网址上的访问前缀‌：浏览器地址栏里‌用什么路径‌能访问到它（对外暴露的入口）。
一个是"库房在哪"，一个是"门店开在哪条街"。两者互相独立，可以随便搭配。
这两个参数是一对"‌一个管磁盘、一个管网址‌"的组合，很多人一开始就混在这儿。先把它们拆开看：

app = Flask(__name__, static_folder='/python/asset', static_url_path='/')
凡是不带前缀的网址(static_url_path='/')，都去 /python/asset 目录里找文件‌。

http://ip:5000/monitor.html → 读 /python/asset/monitor.html

app = Flask(__name__, static_folder='/python/asset', static_url_path='/abc')
凡是带前缀的网址(static_url_path='/abc')，都去 /python/asset 目录里找文件‌。

http://ip:5000/abc/monitor.html → 读 /python/asset/monitor.html
'''

# 字典形式，安装了 supervisor 的本机或远程服务器的ip、登陆端口、用户名、密码信息
serverDict = {
    "node01":{
        "ip":"192.168.1.121",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "node02":{
        "ip":"192.168.1.122",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "node03":{
        "ip":"192.168.1.123",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "node04":{
        "ip":"192.168.1.124",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    }
}
'''
nodeDict = {
    "192.168.1.121:8000":{
        "nodename":"node01",
        "ip":"192.168.1.121",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "192.168.1.122:8000":{
        "nodename":"node02",
        "ip":"192.168.1.122",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "192.168.1.123:8000":{
        "nodename":"node03",
        "ip":"192.168.1.123",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "192.168.1.124:8000":{
        "nodename":"node04",
        "ip":"192.168.1.124",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    }
}
'''

def format_server(sDict):
    # 直观写法：逐一遍历，用"ip:端口"作为key（推荐）
    '''
    {
        "192.168.1.121:8000": {
            "nodename": "node01",
            "ip": "192.168.1.121",
            "port": "8000",
            "user": "admin",
            "passwd": "admin"
        },
        "192.168.1.121:8001": {
            "nodename": "node02",
            "ip": "192.168.1.121",
            "port": "8001",
            "user": "admin",
            "passwd": "admin"
        },
    }
    '''
    nDict = {}
    for node_name, info in sDict.items():
        ip = info["ip"]
        port = info["port"]
        key = f"{ip}:{port}"  # 自动组合键，同IP不同端口也不会互相覆盖
        nDict[key] = {
            "nodename": node_name,
            "ip": ip,
            "port": port,
            "user": info["user"],
            "passwd": info["passwd"]
        }
    return nDict


# 自定义带超时的XML-RPC传输器，官方标准写法
class RpcTimeoutTransport(Transport):
    def __init__(self, timeout=3, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = timeout
    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self.timeout # 给底层 socket 设置超时，到点自动断开抛异常
        return conn

class ProcessFlapDetector:
    def __init__(
        self,
        window_seconds=120,   # 统计时间窗口：最近120秒(时间跨度大一点，因为 prc 后台定时更新，不是实时的)
        flap_threshold=3,     # 窗口内切换超过3次就算抖动
        stable_seconds=120    # 连续稳定2分钟，自动解除抖动标记
    ):
        self.window = window_seconds
        self.threshold = flap_threshold
        self.stable_window = stable_seconds
        
        # 存每个进程的状态历史：key=服务器IP:端口+进程名（唯一标识），value= [(时间戳, 状态码), ...]
        self.state_history = {}
        
        # 存每个进程的抖动标记：key=服务器IP:端口+进程名（唯一标识），value=标记开始时间戳
        self.flapping = {}
        
        # key=服务器IP:端口+进程名（唯一标识），value=(最后切换时间戳, 最后状态)
        self.last_switch = {}
        
        self.lock = Lock() # 多线程安全锁，避免并发写冲突

    def _get_process_key(self, node, process_name):
        """生成进程唯一标识，不同节点同名进程不冲突"""
        return f"{node}:{process_name}"

    def check(self, node, process_name, current_state):
        """
        每次拿到进程最新状态后调用，返回是否抖动、切换次数
        :return: (is_flapping: bool, flap_count: int)
        """
        key = self._get_process_key(node, process_name)
        now = time.time()
        with self.lock:
            history = self.state_history.get(key, [])
            
            # 1. 判断状态是不是变了（和上一次不一样才算一次切换）
            # 状态必须是 STARTING: 10, RUNNING: 20, 因为其它状态都是可控的，不可能成为抖动
            if not history or history[-1][1] != current_state and current_state in (10, 20):
                history.append((now, current_state))
                
            # 2. 存入每个进程的状态历史
            self.state_history[key] = history
            
            # 3. 记最新一次切换的时间和状态
            self.last_switch[key] = (history[-1][0], history[-1][1])
            
            # 4. 提取时间窗口内的历史记录，计算最近时间窗口内状态切换多少次
            history_window = [(t, s) for t, s in history if now - t <= self.window]
            flap_count = len(history_window) - 1 # 历史长度-1就是切换次数
            
            # 5. 状态不变的持续时间
            last_switch_time, _ = self.last_switch[key]
            stable_duration = now - last_switch_time
            
            # 6. 判定是否触发抖动标记
            if flap_count >= self.threshold:
                self.flapping[key] = now
            
            # 7. 判定状态不变的持续时间是否足够长，足够长则"删除抖动标记" 或者 "不删除抖动标记"交给后面程序处理
            else:
                if key in self.flapping and stable_duration >= self.stable_window:
                    #del self.flapping[key]#这里不删除抖动标记，交给后面程序处理
                    self.state_history[key] = []#清除状态历史记录，节省内存空间
            
            is_flapping = key in self.flapping
            return is_flapping, flap_count
    
    def clear_one(self, node, process_name):
        """
        手动清空单个进程的历史记录
        """
        key = self._get_process_key(node, process_name)
        with self.lock:
            # 彻底删除这个进程的所有记录，下次上报重新初始化
            self.state_history.pop(key, None)
            self.last_switch.pop(key, None)
            self.flapping.pop(key, None)
            ts = now_str(fmt)
            print(f"[{ts}][手动清空] {key} 历史已清空")


# 全局唯一实例，所有线程共用
flap_detector = ProcessFlapDetector()

# 格式化字典
nodeDict = format_server(serverDict)


##################################################################################


@app.route('/api/ack_flap', methods=['POST'])
def ack_flap():
    """确认处理抖动，清除后端标记，刷新也不会回来"""
    data = request.json
    node = data.get('node') # 你模板里渲染的时候把参数带上就行
    proc_name = data.get('proc_name')
    
    # 真清后端的标记和历史，下次刷新就不会再返回is_flapping=true
    flap_detector.clear_one(node, proc_name)
    return jsonify(code=200)


def getUrlRpc(node, ndict):
    info = ndict[node]
    return "http://"+info["user"]+":"+info["passwd"]+"@"+node+"/RPC2"


def format_supervisor_data(process_list):
    """
    核心逻辑：根据 group 字段的重复次数来判定是否为组。
    - 出现 >= 2 次的 group 名：视为“组”，聚合在一起。
    - 出现 == 1 次的 group 名：视为“独立进程”，单独展示。
    
    {
        'groups': [
            {
                'group_name': 'push',
                'processes': [
                    {
                        'name': '2-flask_app443',
                        'group': 'push',
                        'state': 20,
                        'statename': 'RUNNING',
                        ...
                        'is_flapping': False,
                        'flap_count': 1,
                        'state_tip': ''
                    }
                ]
            }
        ],
        'ungrouped': [
            {
                'name': 'xxx',
                'group': 'xxx',
                'state': 20,
                'statename': 'RUNNING',
                ...
                'is_flapping': False,
                'flap_count': 0,
                'state_tip': ''
            },
            {
                'name': 'yyy',
                'group': 'yyy',
                'state': 0,
                'statename': 'STOPPED',
                ...
                'is_flapping': True, 
                'flap_count': 3, 
                'state_tip': '因频繁抖动，已被终止，请处理！'
            }
        ]
    }
    
    """
    
    if not process_list:
        return {"groups": [], "ungrouped": []}

    # 第一步：统计每个 group 名称出现的次数
    group_counts = Counter([proc.get('group') for proc in process_list])

    temp_groups = {}
    ungrouped = []

    for proc in process_list:
        g_name = proc.get('group')
        
        # 第二步：根据出现次数分类
        if group_counts[g_name] >= 2:
            # 如果该组名出现多次，归入组集合
            if g_name not in temp_groups:
                temp_groups[g_name] = []
            temp_groups[g_name].append(proc)
        else:
            # 如果该组名只出现一次，归入独立进程
            ungrouped.append(proc)

    # 第三步：构建最终结构
    final_groups = []
    for g_name, procs in temp_groups.items():
        # 可选：按组内进程的 name 排序，保持界面稳定
        procs.sort(key=lambda x: x.get('name', ''))
        final_groups.append({
            "group_name": g_name,
            "processes": procs
        })
    
    # 对组列表本身也进行排序
    final_groups.sort(key=lambda x: x['group_name'])
    
    # 对独立进程列表排序
    ungrouped.sort(key=lambda x: x.get('name', ''))
    
    return {
        "groups": final_groups,
        "ungrouped": ungrouped
    }

'''
#定义一个函数,把它传递给前端
def getAllInfo(node):
    # 自定义函数获取rpc地址
    url = getUrlRpc(node, nodeDict)
    server = ServerProxy(url)
    process_list = server.supervisor.getAllProcessInfo()
    supervisor_data = format_supervisor_data(process_list)
    return supervisor_data
'''


# 你原来的函数，只需要加server_ip参数（你调用的时候传当前服务器IP就行）
# 如果用HTTPS访问RPC，把 Transport 换成 SafeTransport 就行，大部分Supervisor RPC都是HTTP，直接用没问题。
def getAllInfo(node, rpc_timeout=3):
    url = getUrlRpc(node, nodeDict)
    transport = RpcTimeoutTransport(timeout=rpc_timeout)
    server = ServerProxy(url, transport=transport)
    
    try:
        process_list = server.supervisor.getAllProcessInfo()
        # ========== 👇 在这里给每个进程加抖动标记 ==========
        for proc in process_list:
            proc_name = proc['name']
            proc_group = proc['group']
            
            full_name = f"{proc_group}:{proc_name}" if proc_group and proc_group != proc_name else proc_name
            
            current_state = proc['state']
            
            # 检测是否抖动
            is_flapping, flap_count = flap_detector.check(node, full_name, current_state)
            
            # 把标记加到进程数据里，前端/告警逻辑直接用
            proc['is_flapping'] = is_flapping
            proc['flap_count'] = flap_count
            
            #加状态标记，并且状态是 STOPPED: 0，EXITED: 100
            if is_flapping and current_state in (0, 100):
                proc['state_tip'] = "因频繁抖动，已被终止，请处理！"
            elif is_flapping:
                proc['state_tip'] = f"已频繁抖动 {flap_count} 次，请处理！"
            else:
                proc['state_tip'] = ""
                
            """
            进程发生抖动或者抖动达到一定次数，就把此进程停止
            """
            #发生抖动，并且状态已经不是 STOPPED: 0，EXITED: 100
            if is_flapping and current_state not in (0, 100):
                # 停止进程 False 表示非阻塞，默认 True 阻塞
                # ★ wait=False：发完停止命令立即返回，不等待进程退出，绝对不阻塞
                server.supervisor.stopProcess(full_name, False)
                ts = now_str(fmt)
                print(f"[{ts}][自动停止] {node}:{full_name} 抖动{flap_count}次，已停止")
            
        # ==================================================
        return format_supervisor_data(process_list)
    except Exception as e:
        ts = now_str(fmt)
        print(f"[{ts}][RPC失败] {node}: {e}")
        return []
    finally:
        transport.close()# 关闭连接，避免连接泄漏


# 为 getAllInfo 函数设置请求超时时长，超过自定义的时长，单位秒，则返回自定义内容
# 为了防止长时间获取不到 getAllProcessInfo 返回的信息，导致出错
def getAllInfoTimeOut(node, total_timeout=3):
    """
    线程安全超时函数，子线程/主线程都能用，多调用互不干扰
    :param node: 传给 getAllInfo 的参数 ip:port
    :param total_timeout: 超时时长，默认3秒
    """
    try:
        # 提交任务到线程池跑，超时直接返回
        future = RPC_EXECUTOR.submit(getAllInfo, node)
        return future.result(timeout=total_timeout)
    except FuturesTimeoutError:
        ts = now_str(fmt)
        print(f"[{ts}][超时] 服务器 {node} 连接超时，超过{total_timeout}秒无响应")
        return []
    except Exception as e:
        ts = now_str(fmt)
        print(f"[{ts}][错误] 服务器 {node} 连接失败: {str(e)}")
        # 要打详细错误栈就开下面这行
        # traceback.print_exc()
        return []


@app.route("/getenv")
def index_getenv():
    return os.getenv('prompt1') # gunicorn 配置文件中定义的变量
    

@app.route("/")
def index():
    return render_template("monit.html", envtest=os.getenv('prompt1'), sdict=nodeDict, funAllInfo=getAllInfoTimeOut)#渲染模板页面


# 重启 supervisor
@app.route("/restartSupervisor")
def restartSupervisor():
    # 自定义函数获取rpc地址
    node = request.args['node'] # pyweb1
    url = getUrlRpc(node,nodeDict)
    server = ServerProxy(url)
    server.supervisor.restart()
    # 执行跳转到 /restartSupervisor?message=restartSupervisor_192.168.1.121:8000
    return redirect(url_for('index',message="restartSupervisor_"+node))


# 开始或停止某个进程
# 操作组内的程序时，要把组名与程序名用冒号连接，变成 组名:程序名
#亲测验证：当进程名与组名重名时，可以直接使用进程名，
#此时组名对此进程依然有效，继续支持使用组名:进程名进行操作，
#也继续支持对此组名进行操作，命令也会影响到此进程
@app.route("/startOrStop.html")
def index_one():
    para = request.args['name']
    method = request.args['method']
    node = request.args['node']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(node,nodeDict)
    server = ServerProxy(url)
    calls = [
        {'methodName':method, 'params': [para]},
        
      ]

    server.system.multicall(calls)
    return redirect(url_for('index'))


# 重启全部进程
@app.route("/restartAll.html")
def index_restartAll():
    node = request.args['node']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(node,nodeDict)
    server = ServerProxy(url)
    calls = [ 
        {'methodName':'supervisor.stopAllProcesses', 'params': []},
        {'methodName':'supervisor.startAllProcesses', 'params': []},
        
      ]

    server.system.multicall(calls)
    return redirect(url_for('index'))


# 重启某个进程
@app.route("/restartOne.html")
def index_restartOne():
    para = request.args['name']
    node = request.args['node']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(node,nodeDict)
    server = ServerProxy(url)
    calls = [ 
        {'methodName':'supervisor.stopProcess', 'params': [para]},
        {'methodName':'supervisor.startProcess', 'params': [para]},
        
      ]

    server.system.multicall(calls)
    return redirect(url_for('index'))


# 重启某个组
@app.route("/restartGroup.html")
def index_restartGroup():
    para = request.args['name']
    node = request.args['node']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(node,nodeDict)
    server = ServerProxy(url)
    calls = [ 
        {'methodName':'supervisor.stopProcessGroup', 'params': [para]},
        {'methodName':'supervisor.startProcessGroup', 'params': [para]},
        
      ]

    server.system.multicall(calls)
    return redirect(url_for('index'))


@app.route("/allconfiginfo.html")
def get_allConfigInfo():
    
    url = "http://admin:admin@192.168.1.121:8000/RPC2"
    server = ServerProxy(url)
    allConfigInfo = server.supervisor.getAllConfigInfo()
    
    return allConfigInfo


@app.route("/methods.html")
def get_methods():
    
    url = "http://admin:admin@192.168.1.121:8000/RPC2"
    server = ServerProxy(url)
    Methods = server.system.listMethods()
    
    return Methods


'''
# 多重调用，比如：先停止，再启动，这时需要使用 server.system.multicall(calls)
# 如果只是单独停止，可以直接使用 server.supervisor.stopProcess(name)
@app.route('/process_route', methods = ['GET', 'POST'])
def background_process():
    url = "http://admin:admin@192.168.1.121:8000/RPC2"
    server = ServerProxy(url)
    server.supervisor.stopProcess("flask_app443")
    return redirect(url_for('index'))


@app.route('/test123')
def test():
    return '这是测试页面' +"<br/>"+ request.url +"<br/>"+ request.base_url +"<br/>"+ request.host_url+"<br/>"+request.host+"<br/>"+request.path+"<br/>"+request.full_path+"<br/>"+request.url_root

@app.route('/demo')
def demo():
    # 生成包含查询参数的 URL
    url_with_params = url_for('test', name='tom', age='12') # /test123?name=tom&age=12
    
    # 生成纯净的 URL
    url_clean = url_for('test') # /test123
    
    # 拼接并返回 HTML 内容
    html_content = f"{url_with_params}<br/>{url_clean}"
    return html_content


@app.route("/urlfor")
def urlfor():
    # 访问 /urlfor?a=1&b=2 返回 {"k":["1","2"]}
    a = request.args.get('a') #a=1没有时，返回 null
    b = request.args['b'] #b=2必须要有, 不然报错 Bad Request
    return jsonify({'k': [a, b]})

'''

#以下命令，只有在使用 python this.py 才起作用
if __name__=='__main__':
    app.run(debug=True,host='0.0.0.0', port=5000)
