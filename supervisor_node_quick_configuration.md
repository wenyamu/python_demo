## 主配置文件的后缀必须是conf，其引用的配置文件可以是 ini、conf 等
> Supervisor 配置文件通常命名为 supervisord.conf，它被 supervisord 和 supervisorctl 共同使用。如果任一应用程序在启动时未指定选项 -c（该选项用于显式告知应用程序配置文件的名称），应用程序将查找名为 supervisord.conf 的文件。
> 
> https://supervisord.org/configuration.html?highlight=Configuration
> 
> 我就遇到过把主配置文件生成为ini `echo_supervisord_conf > /etc/supervisor/supervisord.ini`，启动 supervisor 时用 -c 指定了此配置文件，但是在我使用 supervisorctl 命令时，直接提示错误，必须指定配置文件才行。
> 
> 我明明没有配置 9001 端口，我配置的是 `[inet_http_server] port = 0.0.0.0:8000` 并且通过 `http://192.168.1.121:8000/` 可以控制进程的启动、停止、重启。
```
root@localhost:~# TZ=Asia/Shanghai /usr/local/bin/supervisord -c /etc/supervisor/supervisord.ini
root@localhost:~# supervisorctl status all
http://localhost:9001 refused connection
root@localhost:~# supervisorctl reload
error: <class 'ConnectionRefusedError'>, [Errno 111] Connection refused: file: /usr/lib/python3.11/socket.py line: 836
root@localhost:~# ps -ef | grep supervisord
root        1245       1  0 09:41 ?        00:00:00 /usr/bin/python3 /usr/local/bin/supervisord -c /etc/supervisor/supervisord.ini
root        1275    1239  0 09:42 pts/0    00:00:00 grep supervisord
root@localhost:~# supervisorctl status
http://localhost:9001 refused connection
root@localhost:~# supervisorctl -s http://localhost:8000
Server requires authentication
Username:admin
Password:

Multi-resolution                 RUNNING   pid 1721, uptime 0:00:14
state_broadcaster                RUNNING   pid 1469, uptime 0:18:37
root@localhost:~# supervisorctl -c /etc/supervisor/supervisord.ini status
Multi-resolution                 RUNNING   pid 1945, uptime 0:00:06
state_broadcaster                RUNNING   pid 1469, uptime 0:38:01
root@localhost:~# supervisorctl status
unix:///tmp/supervisor.sock no such file
root@localhost:~# TZ=Asia/Shanghai /usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
root@localhost:~# supervisorctl status
Multi-resolution                 RUNNING   pid 2177, uptime 0:00:04
state_broadcaster                RUNNING   pid 2176, uptime 0:00:04
root@localhost:~# supervisorctl reload
Restarted supervisord
```
### 安装及初始化配置
```
apt install -y build-essential python3-dev libevent-dev websockets && \
python3 -m pip install supervisor && \
mkdir -p /etc/supervisor && \
echo_supervisord_conf > /etc/supervisor/supervisord.conf && \
cp /etc/supervisor/supervisord.conf /etc/supervisor/supervisord.conf.bak && \
grep -Ev '^\s*[;#]' /etc/supervisor/supervisord.conf.bak | cat -s > /etc/supervisor/supervisord.conf
```

### 配置主配置
```
cat >> /etc/supervisor/supervisord.conf <<EOF
# web管理界面
[inet_http_server]
port = 0.0.0.0:8000
username = admin
password = admin

# 引入需要管理的程序配置文件
[include]
files = /etc/supervisor/my_config/*.conf
EOF
```

### 配置子程序配置项，此配置项不同的程序有不同的设置
```
mkdir -p /etc/supervisor/my_config && \
cat > /etc/supervisor/my_config/time_app.conf <<EOF
[program:time_app]
;标准推荐范围为 0-999 ‌默认值‌：‌999‌ ‌规则‌：‌数值越小，优先级越高，越先启动‌。
; priority=11
;创建该项目用户
user = root

;应用目录，hls_abr_gen.py 存放目录 /root/test
directory = /root/test

;ffmpeg程序命令
;command = python3 hls_abr_gen.py -i rtmp://1.2.3.4:1935/show-flv/abc123456 -o /mnt/hls3 --run
command = python3 -c "import time; f=open('/tmp/strftime.log','w'); [f.seek(0) or f.write(time.strftime('%%Y-%%m-%%d %%H:%%M:%%S\n')) or f.truncate() or f.flush() or time.sleep(1) for _ in iter(int,1)]"

autostart = true ;在supervisord启动的时候，false 表示不自动启动，true 表示随着启动
autorestart = true ;程序异常退出后，false 表示不自动重启，true 表示自动重启
startsecs = 3 ;稳定运行N秒后，从“正在启动”转成“正在运行”状态，值为0表示无需保持运行特定时长。
startretries = 3 ;进程启动失败后，最大尝试的次数。当超过3次后，supervisor将把此进程的状态置为FATAL
stopasgroup = true ;确保关闭supervisord时停止所有相关子进程
killasgroup = true ;确保关闭supervisord时停止所有相关子进程
environment=TZ="Asia/Shanghai"  # 单独给进程设上海时区，只修改此程序的环境变量

;日志目录必须事先存在，不然会出错
;stdout_logfile = /tmp/time_app_out.log
;stderr_logfile = /tmp/time_app_err.log

[eventlistener:state_broadcaster]
command=python3 /etc/supervisor/listener.py
events=PROCESS_STATE
buffer_size=10
; 监听器挂掉后自动重启
autorestart=true
startsecs=1
EOF
```

### 运行
```
TZ=Asia/Shanghai /usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
```

### 设置开机启动
> 如果是通过 `apt install supervisor`安装的，本身就自带开机自启，以下配置可以忽略
>
> 以下写入的自启动配置文件，是直接复制通过 apt 安装的 supervisor 的自启动配置文件，没有作任何修改
```
cat > /etc/systemd/system/supervisord.service <<EOF
[Unit]
Description=Supervisor process control system for UNIX
Documentation=http://supervisord.org
After=network.target

[Service]
Type=forking
ExecStart=/usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
ExecStop=/usr/local/bin/supervisorctl $OPTIONS shutdown
ExecReload=/usr/local/bin/supervisorctl $OPTIONS reload
KillMode=process
Restart=on-failure
RestartSec=30s

[Install]
WantedBy=multi-user.target
EOF
```

### 常用命令
```
systemctl daemon-reload        # 重新加载服务文件
systemctl enable supervisord   # 开启自启
systemctl start supervisord    # 启动
# 验证
systemctl status supervisord   #查看
supervisorctl status           # 能看到你所有程序的状态就说明成功了
systemctl is-enabled supervisord #检查开机自启是否成功，返回 enabled 则表示成功

systemctl restart supervisord  #重启
systemctl stop supervisord     #停止
systemctl reload supervisord   #暂未研究 与 supervisorctl reload 是否效果一样
```

### 操作演示
```
root@localhost:~# systemctl daemon-reload
root@localhost:~# systemctl enable supervisord
Created symlink /etc/systemd/system/multi-user.target.wants/supervisord.service → /etc/systemd/system/supervisord.service.
root@localhost:~# systemctl start supervisord
root@localhost:~# systemctl status supervisord
● supervisord.service - Supervisor process control system for UNIX
     Loaded: loaded (/etc/systemd/system/supervisord.service; enabled; vendor preset: enabled)
     Active: active (running) since Wed 2026-11-04 12:42:18 CST; 2s ago
       Docs: http://supervisord.org
    Process: 1180 ExecStart=/usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf (code=exited, status=0/SUCCESS)
   Main PID: 1182 (supervisord)
      Tasks: 5 (limit: 410)
     Memory: 31.7M
        CPU: 3.028s
     CGroup: /system.slice/supervisord.service
             ├─1182 /usr/bin/python3 /usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
             ├─1183 python3 /etc/supervisor/listener.py
             └─1184 python3 -c import time; f=open('/tmp/strftime.log','w'); [f.seek(0) or f.write(time.strftime('%Y-%m-%d %H:%M:%S\n')) or f.truncate() or f.flush() or time.sleep(1) for _ in iter(int,1)]
root@localhost:~# supervisorctl status
1-time_app                       RUNNING   pid 970, uptime 0:01:13
2-state_broadcaster              RUNNING   pid 969, uptime 0:01:13
root@localhost:~# systemctl is-enabled supervisord
enabled
```
