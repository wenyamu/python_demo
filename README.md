
python flask gunicorn supervisor 演示文件

搞懂 flask gunicorn supervisor 的作用和关系

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
### 生成默认配置文件
```
mkdir -p /etc/supervisor && \
echo_supervisord_conf > /etc/supervisor/supervisord.conf
```

### 启动 supervisor
> supervisor 的默认监控 http://0.0.0.0:8000
>
> 只能管理本机的程序
```
/usr/local/bin/supervisord -c /python/supervisor_flaskapp.conf
```

### 启动自定义监控程序
> 自定义的监控 http://0.0.0.0:5000
>
> 可以管理远程服务器的 supervisor 和 程序
```
# 先修改 /python/supervisor_monit/monit.py 中的字典形式的参数
# 以下是安装了 supervisor 的本机或远程服务器的ip、登陆端口、用户名、密码信息
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
```
# 当配置文件 gconf_monit.py 中未指定 chdir 时，
# 需要进入 monit.py 所在的目录，不然会出现错误提示
# ModuleNotFoundError: No module named 'monit'
cd /python/supervisor_monit
gunicorn -c /python/supervisor_monit/gconf_monit.py monit:app --preload
```

### 各文件的功能说明

flasktest.py
> web程序文件，是用 python 写的 web 页的功能代码。类似于 php 写的 web 页 xxx.php 文件是一个意思。

gconf80.py
> 作为启动 gunicorn 的配置文件，对 gunicorn 的监听端口，线程数等参数进行设置。

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
```
supervisor_flaskapp.conf
> 作为启动 supervisor 时的主配置文件，主配置文件中会引入 flask80.conf 子配置文件。
