### 安装 docker 容器
```
docker compose -f python.yml up -d
```

### 进入容器
```
docker exec -it pythontest sh
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
import time, datetime, os

# ========== 配置项，想改就改这里 ==========
LOG_PATH = '/etc/supervisor/power_test.log'  # 日志路径
MAX_LINES = 100                     # 最多保留的行数，超过就删开头
CHECK_INTERVAL = 10                 # 每写100行检查一次（不用改，减少SD卡写入）
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

### 运行 supervisor
```
TZ=Asia/Shanghai /usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
```
