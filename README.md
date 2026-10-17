
python flask gunicorn supervisor 演示文件

搞懂 flask gunicorn supervisor 的作用和关系

> 注意：supervisor 有两种安装方式，一种是 `apt install supervisor`，另一种是 `pip install supervisor`
> 
> 区别是 pip 安装的不会自动生成 `/etc/supervisor/supervisord.conf` 配置文件，需要手动生成，见后面的操作命令

### 下载本项目
> 本项目的配置文件，都是基于 /python 目录创建的
```
git clone https://github.com/wenyamu/python_demo.git /python
```

### 安装依赖项及软件
```
apt install -y build-essential python3-dev libevent-dev && \
python3 -m pip install gunicorn flask gevent pymysql supervisor
```

### 查看软件版本
```
root@orangepizero3:~# python3 -m pip list
Package             Version
------------------- -----------
Flask               3.1.3
gevent              26.7.0
gunicorn            23.0.0
PyMySQL             1.2.3
supervisor          4.3.0
```

### 生成默认配置文件
```
mkdir -p /etc/supervisor && \
echo_supervisord_conf > /etc/supervisor/supervisord.conf
```

### 启动 supervisor
> supervisor 的默认监控 http://0.0.0.0:8000
>
> 只能管理本机的程序

#### 修改配置文件中的本地服务器ip、登陆端口、用户名、密码信息，用于supervisor 的默认监控的登陆
> /python/supervisor_flaskapp.conf
```
#web管理界面
[inet_http_server]
port = 0.0.0.0:8000
username = admin
password = admin
```
#### 运行
```
/usr/local/bin/supervisord -c /python/supervisor_flaskapp.conf
```

### 启动自定义监控程序
> 自定义的监控 http://0.0.0.0:5000
>
> 可以管理本机和远程服务器的 supervisor 和 程序
```
# 先修改 /python/supervisor_monit/monit.py 中的字典形式的参数
# 以下是安装了 supervisor 的本机和远程服务器的ip、登陆端口、用户名、密码信息
serverDict = {
    "pyweb1":{
        "host":"192.168.1.100",
        "port":"8000",
        "user":"admin",
        "passwd":"admin",
    },
    "pyweb2":{
        "host":"192.168.1.101",
        "port":"8001",
        "user":"admin",
        "passwd":"admin",
    },
    "pyweb3":{
        "host":"192.168.1.102",
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
> 把配置文件 `/python/supervisor_monit/flask_monit.conf` 加入到主配置文件 `/python/supervisor_flaskapp.conf` 中, 如下：
```
[include]
files = /etc/supervisor/supervisord.conf /python/supervisor_conf/*.conf /python/supervisor_monit/*.conf
```

### 各文件的功能说明

flasktest.py
> web程序文件，是用 python 写的 web 页的功能代码。类似于 php 写的 web 页 xxx.php 文件是一个意思。
> 
> 直接访问 http://0.0.0.0
```
from flask import Flask, render_template, url_for, request
import pymysql
app = Flask(__name__,
      template_folder='/python/templates',
      static_folder='/python/asset',
      static_url_path="/",
      )
...
...
```

gconf80.py
> 作为启动 gunicorn 的配置文件，对 gunicorn 的监听端口，线程数等参数进行设置。
```
...
...
#debug = True # 调试模式运行
daemon = False # 守护Gunicorn进程，默认False(即不让其在后台运行，而是使用supervisor管理进程)
# True，表示代码更新时将被热载入（不用手动重启进程了）。如果是直接运行gunicorn命令，直接加参数 --reload 即可
reload = True
#绑定与Nginx通信的端口ipv4、ipv6
bind = '0.0.0.0:80'
...
...
```
supervisor_conf/flask80.conf
> 作为 supervisor 管理的子进程的配置文件，对 gunicorn 进程的一些管理。gunicorn 就是用来启动 flask web 程序的，示例如下。
```bash
[program:flask_app80]
...
...
#flasktest就是代表flasktest.py，这里不写后缀。app是flasktest.py文件中设置的flask入口名
command = /usr/local/bin/gunicorn -c /python/gconf80.py flasktest:app
autostart = true #在supervisord启动的时候也自动启动
...
...
[program:program1]
...
...
command = python3 xxx.py
autostart = true #在supervisord启动的时候也自动启动
...
...
#把多个进程 program 组成一个组 myapp_group
[group:myapp_group]
programs=program1,program2,program3
...
...
```
supervisor_flaskapp.conf
> 作为启动 supervisor 时的主配置文件，主配置文件中会引入 flask80.conf 子配置文件。
```bash
...
...
[include]
files = /etc/supervisor/supervisord.conf /python/supervisor_conf/*.conf /python/supervisor_monit/*.conf

#web管理界面
[inet_http_server]
port = 0.0.0.0:8000
username = admin
password = admin
...
...
```

### 附言
> supervisor 命令
```
#启动、停止、重启应用、查看状态
supervisorctl start flask_app80
supervisorctl stop flask_app443
supervisorctl stop all #停止全部
supervisorctl restart flask_app80 # 重启，注意这里不会重新加载配置文件
supervisorctl status flask_app80
supervisorctl status all

#对组的操作, 后面必须加上:(冒号)，不然会认为是 program
supervisorctl start myapp_group:

#操作组内的程序时，要把组名与程序名用冒号连接，变成 组名:程序名
supervisorctl start myapp_group:program1

root@orangepizero3:~# supervisorctl restart program1
program1: ERROR (no such process)
program1: ERROR (no such process)
root@orangepizero3:~# supervisorctl restart myapp_group:program1
myapp_group:program1: stopped
myapp_group:program1: started

#重启主进程 supervisord，重新加载配置文件，重新启动正在运行的所有程序
# supervisord 进程的 pid 不会更新
supervisorctl reload

#终止supervisord进程和被supervisord管理的子进程
#如果gunicorn配置文件中daemon = False，则也会终止gunicorn
supervisorctl shutdown

supervisorctl reread && supervisorctl update

#预读取配置(会检测配置文件，找出配置有改动的程序，并列出程序名)
[root@localhost ~]# supervisorctl reread
flask_app80: changed

#更新进程组:根据预读取的配置文件，启动新程序或重启配置有改动的程序
#配置没有改动的程序不会受影响
[root@localhost ~]# supervisorctl update
flask_app80: stopped
flask_app80: updated process group
[root@localhost ~]#
```
