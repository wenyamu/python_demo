from xmlrpc.client import ServerProxy
import signal

if __name__ == '__main__':
  server = ServerProxy("http://admin:admin@8.210.236.200:8002/RPC2")

  # 停止
  # print(server.supervisor.stopProcess("flask_app443"))
  # print(server.supervisor.stopAllProcesses())  
  # print(server.supervisor.stopProcessGroup(name))
  
  # 查看基本信息
  # print(server.supervisor.getProcessInfo("flask_app443"))
  # print(server.supervisor.getAllProcessInfo())
  
  # 启动
  # print(server.supervisor.startProcess("flask_app443"))
  # print(server.supervisor.startAllProcesses())
  # print(server.supervisor.startProcessGroup(name))
  
  # 添加、删除进程组
  # print(server.supervisor.addProcessGroup("notes"))
  # print(server.supervisor.removeProcessGroup("notes"))
  
  # 重新加载配置
  # print(server.supervisor.reloadConfig())

  # 查看、清空子进程日志
  # print(server.supervisor.readProcessStderrLog("flask_app443",0,2048))
  # print(server.supervisor.readProcessStdoutLog("flask_app443",0,2048))
  # print(server.supervisor.tailProcessStderrLog("flask_app443",0,512))
  # print(server.supervisor.tailProcessStdoutLog("flask_app443",0,512))
  # print(server.supervisor.clearProcessLogs("flask_app443"))
  # print(server.supervisor.clearAllProcessLogs())
  
  # 以下是对supervisor主进程的操作
  
  # 查看、清空supervisor主进程日志
  # print(server.supervisor.readLog(0,4096))
  # print(server.supervisor.clearLog())
  
  # 结束主进程
  # print(server.supervisor.shutdown())
  
  # 重启主进程
  # print(server.supervisor.restart())

  # 获取主进程pid
  # print(server.supervisor.getPID())

  # print(server.supervisor.getState())

  # print(server.supervisor.getAPIVersion())
  # print(server.supervisor.getSupervisorVersion())
  # print(server.supervisor.getIdentification())
  
  # print(server.system.listMethods())
  # print(server.system.methodHelp("system.multicall"))
  # print(server.system.methodSignature("supervisor.restart"))
  
  ################# server.system.multicall() 多个信息
  # print(server.system.multicall([{'methodName':'supervisor.readProcessStderrLog', 'params': ["flask_app443",0,2048]}]))
  
  calls = [
    # {'methodName':'supervisor.stopProcess', 'params': ["flask_app443"]},
    # {'methodName':'supervisor.startProcess', 'params': ["flask_app443"]},
    {'methodName':'supervisor.getProcessInfo', 'params': ["flask_app80"]},
     #{'methodName':'supervisor.getAllProcessInfo', 'params': []},
      
  ]
  #print(server.system.multicall(calls))
  
  ################################### 分隔
  
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
    }
  }

  calls = [
    {'methodName':'supervisor.getAllProcessInfo', 'params': []},
  ]

  def getUrlRpc(name, sdict):
    r = sdict[name]
    return "http://"+r["user"]+":"+r["passwd"]+"@"+r["host"]+":"+r["port"]+"/RPC2"

  #定义一个函数,把它传递给前端
  def getAllInfo(title):
    # 自定义函数获取rpc地址
    url = getUrlRpc(title, serverDict)
    server = ServerProxy(url)
    return server.system.multicall(calls)
  
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

  print(getAllInfoTimeOut("pyweb3"))
  

  