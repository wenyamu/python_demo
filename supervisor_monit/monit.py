from flask import Flask, render_template, url_for, request, jsonify, redirect
from xmlrpc.client import ServerProxy
import signal
import os

app = Flask(__name__,
            template_folder='/python/supervisor_monit/templates',
            static_folder='/python/supervisor_monit/asset',
            static_url_path="/",
            )

# __name__ 本文件的文件名（不含后缀）
# template_folder 存放模板的目录，缺省值为当前项目目录下的templates目录
# static_folder 存放静态文件的目录（注意：存放在此目录下的文件，都会被当成静态文件处理，例如php、py文件），通常存放css/js/jpg/html等文件（假设项目的绝对路径为"/py",如果参数值为"/py/sss"时，可以直接通过xxx.com/sss/x.jpg 进行访问，此时static_folder的值做为存放目录以及url访问），缺省值为当前项目目录下的static目录
# static_url_path 访问静态文件的路由设置，可以配合static_folder使用，例如：当static_url_path参数值为"/aaa"时，可以直接通过xxx.com/aaa/x.jpg 进行访问，此时static_folder的值仅做为存放目录，不作为url访问

@app.route("/getenv")
def index_getenv():
    return os.getenv('ljs2') # gunicorn 配置文件中定义的变量

# 字典形式
serverDict = {
    "pyweb1":{
        "host":"8.210.236.200",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "pyweb2":{
        "host":"8.210.236.200",
        "port":"8001",
        "user":"admin",
        "passwd":"admin",
    },
    "pyweb3":{
        "host":"8.210.236.200",
        "port":"8002",
        "user":"admin",
        "passwd":"admin",
    }
}

def getUrlRpc(name, sdict):
    r = sdict[name]
    return "http://"+r["user"]+":"+r["passwd"]+"@"+r["host"]+":"+r["port"]+"/RPC2"

#定义一个函数,把它传递给前端
def getAllInfo(title):
    # 自定义函数获取rpc地址
    url = getUrlRpc(title, serverDict)
    server = ServerProxy(url)
    return server.supervisor.getAllProcessInfo()

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
    return render_template("monit.html", envtest=os.getenv('ljs2'), sdict=serverDict, funAllInfo=getAllInfoTimeOut)

# 重启 supervisor
@app.route("/restartSupervisor")
def restartSupervisor():
    # 自定义函数获取rpc地址
    title = request.args['title']
    url = getUrlRpc(title,serverDict)
    server = ServerProxy(url)
    server.supervisor.restart()
    return redirect(url_for('index',message="restartSupervisor_"+title))

# 开始或停止某个进程
@app.route("/one.html")
def index_one():
    para = request.args['name']
    method = request.args['method']
    title = request.args['title']
    # url = "http://admin:admin@8.210.236.200:5002/RPC2"
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
    # url = "http://admin:admin@8.210.236.200:5002/RPC2"
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
    # url = "http://admin:admin@8.210.236.200:5002/RPC2"
    url = getUrlRpc(title,serverDict)
    server = ServerProxy(url)
    calls = [ 
        {'methodName':'supervisor.stopProcess', 'params': [para]},
        {'methodName':'supervisor.startProcess', 'params': [para]},
        
      ]

    server.system.multicall(calls)
    return redirect(url_for('index'))



'''
# //渲染页面，含有执行python函数的按钮
@app.route('/ajaxpy')
def ajax_py():
    return render_template('fun/fun.html')

# //后台执行，ajax调用不会刷新页面
@app.route('/background_process_route', methods = ['GET', 'POST'])
def background_process():
    url = "http://admin:admin@8.210.236.200:5002/RPC2"
    server = ServerProxy(url)
    server.supervisor.stopProcess("flask_app443")
    return redirect(url_for('index'))

@app.route("/urlfor")
def urlfor():
    # return request.args['name']
    #return request.url +"<br/>"+ request.base_url +"<br/>"+ request.host_url+"<br/>"+request.host+"<br/>"+request.path+"<br/>"+request.full_path+"<br/>"+request.url_root
    #return url_for('test')
    # return url_for('test', next='a', nexta='aa')+"<br/>"+url_for('test')
    
    a = request.args.get('a')
    b = request.args.get('b')
    # return a
    return jsonify({'k': [a, b]})
'''



#以下命令，只有在使用 python this.py 才起作用
if __name__=='__main__':
    app.run(debug=True,host='0.0.0.0',port=5000)
