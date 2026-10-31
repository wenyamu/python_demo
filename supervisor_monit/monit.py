from flask import Flask, render_template, url_for, request, jsonify, redirect, Response
from xmlrpc.client import ServerProxy
import signal
import os
from collections import Counter
import json
import threading
import time

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

@app.route("/getenv")
def index_getenv():
    return os.getenv('prompt1') # gunicorn 配置文件中定义的变量

# 字典形式，安装了 supervisor 的本机或远程服务器的ip、登陆端口、用户名、密码信息
serverDict = {
    "node01":{
        "host":"192.168.1.121",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "node02":{
        "host":"192.168.1.122",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "node03":{
        "host":"192.168.1.123",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    }
}

def getUrlRpc(name, sdict):
    r = sdict[name]
    return "http://"+r["user"]+":"+r["passwd"]+"@"+r["host"]+":"+r["port"]+"/RPC2"


def format_supervisor_data(process_list):
    """
    核心逻辑：根据 group 字段的重复次数来判定是否为组。
    - 出现 >= 2 次的 group 名：视为“组”，聚合在一起。
    - 出现 == 1 次的 group 名：视为“独立进程”，单独展示。
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

#定义一个函数,把它传递给前端
def getAllInfo(title):
    # 自定义函数获取rpc地址
    url = getUrlRpc(title, serverDict)
    server = ServerProxy(url)
    process_list = server.supervisor.getAllProcessInfo()
    supervisor_data = format_supervisor_data(process_list)
    return supervisor_data

# 为 getAllInfo 函数设置请求超时时长，超过自定义的时长，单位秒，则返回自定义内容
# 为了防止长时间获取不到 getAllProcessInfo 返回的信息，导致出错

def getAllInfoTimeOut(n):
    def handler(signum, frame):
        raise AssertionError
    try:
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(10) # 设置超时时长，单位秒
        return getAllInfo(n)
    except AssertionError: # 错误类似为 AssertionError 时，执行
        return []
    except: # 当上面没有匹配的错误类似时，执行此条，放在最后
        return []
    finally: # 此代码段不能删除，虽然对页面没有影响，但是后台日志会输出错误
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)

@app.route("/")
def index():
    return render_template("monit.html", envtest=os.getenv('prompt1'), sdict=serverDict, funAllInfo=getAllInfoTimeOut)#渲染模板页面

# 重启 supervisor
@app.route("/restartSupervisor")
def restartSupervisor():
    # 自定义函数获取rpc地址
    title = request.args['title'] # pyweb1
    url = getUrlRpc(title,serverDict)
    server = ServerProxy(url)
    server.supervisor.restart()
    # 执行跳转到 /restartSupervisor?message=restartSupervisor_pyweb1
    return redirect(url_for('index',message="restartSupervisor_"+title))

# 开始或停止某个进程
# 操作组内的程序时，要把组名与程序名用冒号连接，变成 组名:程序名
#亲测验证：当进程名与组名重名时，可以直接使用进程名，
#此时组名对此进程依然有效，继续支持使用组名:进程名进行操作，
#也继续支持对此组名进行操作，命令也会影响到此进程
@app.route("/startOrStop.html")
def index_one():
    para = request.args['name']
    method = request.args['method']
    title = request.args['title']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(title,serverDict)
    server = ServerProxy(url)
    calls = [
        {'methodName':method, 'params': [para]},
        
      ]

    server.system.multicall(calls)
    return redirect(url_for('index'))

# 重启全部进程
@app.route("/restartAll.html")
def index_restartAll():
    title = request.args['title']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(title,serverDict)
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
    title = request.args['title']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(title,serverDict)
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
    title = request.args['title']
    # url = "http://admin:admin@192.168.1.121:8000/RPC2"
    url = getUrlRpc(title,serverDict)
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
