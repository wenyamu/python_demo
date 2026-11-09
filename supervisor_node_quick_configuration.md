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
apt install -y build-essential python3-dev libevent-dev && \
python3 -m pip install supervisor websockets && \
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

### 创建程序文件
```
cat > /etc/supervisor/power_test.py << EOF
import time, datetime, os

# ========== 配置项，想改就改这里 ==========
LOG_PATH = '/etc/supervisor/power_test.log'  # 日志路径
MAX_LINES = 3600     # 最多保留的行数，超过就删开头
CHECK_INTERVAL = 60  # 每写60行检查一次（不用改，减少SD卡写入）
# ========================================

# 强制锁定北京时间，不受系统时钟错乱影响
os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()

def trim_to_max_lines():
    """截断日志，只保留最后MAX_LINES行（原子操作，不会损坏文件）"""
    if not os.path.exists(LOG_PATH):
        return
    with open(LOG_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if len(lines) <= MAX_LINES:
        return
    # 只留最后MAX_LINES行，前面的全删掉
    keep_lines = lines[-MAX_LINES:]
    # 先写临时文件，再原子替换，避免写一半断电损坏原日志
    tmp_path = LOG_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.writelines(keep_lines)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, LOG_PATH)
    
# 启动时先截断一次（处理之前遗留的大文件）
trim_to_max_lines()

def get_uptime():
    """内核开机秒数，不受墙钟跳变影响，断电重启必归零"""
    with open('/proc/uptime') as fp:
        return float(fp.read().split()[0])
    
# 追加模式打开文件，行缓冲
with open(LOG_PATH, 'a', buffering=1, encoding='utf-8') as f:
    proc_start = time.monotonic()
    # 写启动标记
    start_line = (f'\n===== 启动 | 墙钟 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")} '
                  f'| 开机 {get_uptime():.1f}s | PID {os.getpid()} =====\n')
    f.write(start_line)
    f.flush(); os.fsync(f.fileno())
    
    line_count = 0
    while True:
        # 写当前行
        now_ms = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        log_line = (f'{now_ms} | {get_uptime():.1f}s | 运行{time.monotonic()-proc_start:.1f}s\n')
        f.write(log_line)
        f.flush(); os.fsync(f.fileno())
        
        line_count += 1
        # 每写CHECK_INTERVAL行检查一次，超了就截断
        if line_count >= CHECK_INTERVAL:
            trim_to_max_lines()
            line_count = 0
        time.sleep(1)
EOF
```

### 配置子程序配置项
```
mkdir -p /etc/supervisor/my_config && \
cat > /etc/supervisor/my_config/time_app.conf <<EOF
[program:1-time_app]
;标准推荐范围为 0-999 ‌默认值‌：‌999‌ ‌规则‌：‌数值越小，优先级越高，越先启动‌。
; priority=11
;创建该项目用户
user = root

;应用目录，文件的默认存放目录 /root/test
directory = /root/test

;程序命令
;command = tail -f /dev/null #如果只是测试，不想创建程序文件，可以用这一条
command = python3 /etc/supervisor/power_test.py

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

;事件监听器
[eventlistener:2-state_broadcaster]
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
systemctl daemon-reload        # 重新加载服务文件 /etc/systemd/system/supervisord.service
systemctl enable supervisord   # 设置 supervisord 为开机自启

# 验证
systemctl is-enabled supervisord # 检查开机自启是否设置成功，返回 enabled 则表示成功
systemctl status supervisord     # 查看 supervisord 运行状态
supervisorctl status             # 查看 supervisord 所有进程状态，能看到就说明成功了

systemctl start supervisord    # 启动 supervisord
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
