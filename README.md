
## 题外话
> Python 脚本 supervisord 是一个被许多人用来管理进程的强大工具。该工具要求目标系统必须安装庞大的 Python 环境。例如在Docker环境中，Python对我们来说太大了。
> 
> 以下项目是用 GO 语言写的一个 supervisord 非常适合未安装Python的环境。

> 它支持 depends_on 配置项，监督命令启动依赖。如果程序A依赖于程序B、C，则程序B、C将在程序A之前启动。
```
https://github.com/ochinchina/supervisord
```

## 前言，本项目最初的目的，搞懂 python flask gunicorn supervisor 的作用和关系
> 如果想让 supervisor 支持 依赖启动，可以安装以下插件
>
> `https://github.com/bendikro/supervisord-dependent-startup`
> 
> `python3 -m pip install supervisord-dependent-startup`
>
> 或者 `pip install -e git+https://github.com/bendikro/supervisord-dependent-startup.git#egg=supervisord-dependent-startup`

### 下载本项目
> 本项目的配置文件，都是基于 /python 目录创建的
```
git clone https://github.com/wenyamu/python_demo.git /python
```

### 安装依赖项及软件
> 注意：supervisor 有两种安装方式，一种是 `apt install supervisor`，另一种是 `pip install supervisor`
> 
> 区别是 pip 安装的不会自动生成 `/etc/supervisor/supervisord.conf` 配置文件，需要手动生成，见后面的操作命令
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
> 备份配置文件 并去掉注释
```
mkdir -p /etc/supervisor && \
echo_supervisord_conf > /etc/supervisor/supervisord.conf && \
cp /etc/supervisor/supervisord.conf /etc/supervisor/supervisord.conf.bak && \
grep -v "#" /etc/supervisor/supervisord.conf.bak > /etc/supervisor/supervisord.conf
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
> 以北京时间为准
```
TZ=Asia/Shanghai /usr/local/bin/supervisord -c /python/supervisor_flaskapp.conf
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

#预读取配置 和 应用配置项
supervisorctl reread && supervisorctl update

#预读取配置(会检测配置文件，找出配置有改动的程序，并列出程序名)
[root@localhost ~]# supervisorctl reread
flask_app80: changed

#根据预读取的配置文件，启动新程序，停止程序，或重启程序，配置没有改动的程序不会受影响
根据配置文件的变更，它会自动执行以下操作：
‌1.新增进程‌：如果配置文件中添加了新的 [program:x] 段落，它会自动启动这些新进程。
‌2.移除进程‌：如果配置文件中删除了某个 [program:x] 段落，它会自动停止并移除该进程。
‌3.重启变更的进程‌：如果某个已有进程的配置参数（如 command、environment、user 等）发生了修改，它会自动重启该进程以应用新配置。
‌4.忽略未变更的进程‌：对于配置没有发生变化的进程，它不会进行任何操作，保持其运行状态不变。
[root@localhost ~]# supervisorctl update
flask_app80: stopped
flask_app80: updated process group
[root@localhost ~]#

# 注意：reread 只是让 supervisord 知道谁配置变了，而 update 才是真正去执行变更的动作。
supervisorctl reread 操作不是必须的，可以直接执行 supervisorctl update 去执行变更的动作
```

### 插件
#### 依赖启动插件 supervisord-dependent-startup 的使用
>
> 举个例子：app1 > app2 > app3
>
> 程序 app3 需要在 app2 正常运行之后启动，程序 app2 需要在 app1 正常运行之后启动，那么就如下设置
>
> 注意：对于所有依赖其他程序或被其他程序依赖的，autostart 必须都设置为 false, 意思就是把启动权由supervisor交给插件控制
```
[program:app1]
autostart = false
dependent_startup=true

[program:app2]
autostart = false
dependent_startup=true
dependent_startup_wait_for=app1:running

[program:app3]
autostart = false
dependent_startup=true
dependent_startup_wait_for=app2:running
```
#### 配置项使用说明
```
dependent_startup
将此服务标记为由 supervisord-dependent-startup 处理。对于所有依赖其他服务或被其他服务依赖的服务，必须将 dependent_startup 设置为 true

dependent_startup_wait_for
1、要使名为 child 的服务依赖于服务 parent, 这样设置 dependent_startup_wait_for=parent:running
2、多个依赖项由空格分隔。要使名为child的服务依赖于parent1和parent2服务，这样设置 dependent_startup_wait_for=parent1:running parent2:running
事件包括：starting, running, backoff, stopping, exited, fatal
```

#### 设置事件监听器
> 注意：监听模块指定的配置文件，就是启动 supervisor 时的配置文件，这里一定要注意，虽然有点难以理解，但是就是这样的
```
# 事件监听器, 用于启动依赖
[eventlistener:dependent_monitor]
#以模块的方式运行，指定配置文件
command=python3 -m supervisord_dependent_startup -c /python/supervisor_flaskapp.conf
stderr_logfile=/tmp/%(program_name)s-err.log
events=PROCESS_STATE
autostart=true
; The following settings are necessary to ensure the supervisord_dependent_startup
; process exits with EXITED when successfull, and FATAL when an error occured
autorestart=unexpected
startretries=0
exitcodes=0,3
```

