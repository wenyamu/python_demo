### supervisor 监控有两种

#### websockets 版 http://192.168.1.121
> python3 -m pip install websockets
> 
> 需要配置 listener.py 事件监听器，和 html/monitor.html
>
> 优点，可以实时反馈进程事件的状态变化

#### rpc 版 http://192.168.1.121:5000/
> 需要配置 monit.py web启动文件， 和 模板文件 supervisor_monit/templates/monit.html
>
> 可以管理本机和远程服务器的 supervisor 和 程序
>
> 缺点，不能实时的反馈进程事件状态变化
```
# 先修改 /python/supervisor_monit/monit.py 中的字典形式的参数
# 以下是安装了 supervisor 的本机和远程服务器的ip、登陆端口、用户名、密码信息
serverDict = {
    "pyweb1":{
        "ip":"192.168.1.100",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "pyweb2":{
        "ip":"192.168.1.101",
        "port":"8001",
        "user":"admin",
        "passwd":"admin",
    },
    "pyweb3":{
        "ip":"192.168.1.102",
        "port":"8002",
        "user":"admin",
        "passwd":"admin",
    }
}
```
#### 方法一：单独运行
```
# 当配置文件 gconf_monit.py 中未指定 chdir 时，
# 需要进入 monit.py 所在的目录，不然会出现错误提示
# ModuleNotFoundError: No module named 'monit'
cd /python/supervisor_monit
gunicorn -c /python/supervisor_monit/gconf_monit.py monit:app --preload
```

#### 方法二：作为 supervisor 子程序运行
> 本项目已经使用此方法
