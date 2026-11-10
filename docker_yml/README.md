### 安装 docker 容器
```
docker compose -f python.yml up -d
```

### 进入容器
```
docker exec -it supervisortest sh
```

### 安装 supervisor
```
python3 -m pip install supervisor websockets && \
mkdir -p /etc/supervisor && \
echo_supervisord_conf > /etc/supervisor/supervisord.conf && \
cp /etc/supervisor/supervisord.conf /etc/supervisor/supervisord.conf.bak
```

### 配置 supervisor
```
cat >> /etc/supervisor/supervisord.conf <<EOF
# web管理界面
[inet_http_server]
port = 0.0.0.0:9001
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
import time, datetime, os, fcntl

# ========== 配置，要多少行改这里就行，100/1000都可以 ==========
LOG_PATH = '/etc/supervisor/power_test.log'
MAX_LINES = 1000  # 永远最多保留1000行，满了就删最老的
# ==========================================================

os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()

def get_uptime():
    """内核开机秒数，不受墙钟跳变影响，断电重启必归零"""
    with open('/proc/uptime') as fp:
        return float(fp.read().split()[0])

proc_start = time.monotonic()

def append_and_trim():
    """写一行新时间，超出就截断，全程加文件锁，多进程也不会乱"""
    # 1. 先追加最新一行：打开→写→强制落盘→关闭，不持有句柄
    now_us = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')  # 精确到微秒
    log_line = f'{now_us} | 开机{get_uptime():.1f}s | 运行{time.monotonic()-proc_start:.1f}s'
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 加排他锁，防止多进程同时写
        f.write(log_line + '\n')
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    # 2. 检查行数，超了就截断：读所有行→只留最后MAX_LINES行→覆盖写回
    with open(LOG_PATH, 'r+', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        lines = f.readlines()
        if len(lines) > MAX_LINES:
            keep = lines[-MAX_LINES:]
            f.seek(0)
            f.writelines(keep)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

if __name__ == '__main__':
    # 写启动标记
    start_line = (f'\n===== 启动 | 墙钟 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")} '
                  f'| 开机 {get_uptime():.1f}s | PID {os.getpid()} =====\n')
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 加排他锁，防止多进程同时写
        f.write(start_line + '\n')
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    while True:
        append_and_trim()
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

### 运行 supervisor
```
TZ=Asia/Shanghai /usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
```
