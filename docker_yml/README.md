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
cat > /etc/supervisor/power_test.py << 'EOF'
import time, datetime, os
# 强制锁定北京时间，不受系统时区错乱影响
os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()

# 追加模式（不覆盖旧内容，保留完整时间线）
with open('/etc/supervisor/power_test.log', 'a', buffering=1) as f:
    # 每次启动先打一行明显标记，断电重启后一眼就能看到分界点
    start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    f.write(f'\n=== 进程启动 @ {start_time} ===\n')
    f.flush()
    os.fsync(f.fileno())  # 强制立刻写磁盘，不留在内存缓冲，断电最多丢最后1行

    while True:
        # 精确到毫秒（%f是微秒，截前3位就是毫秒）
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        f.write(now + '\n')
        f.flush()
        os.fsync(f.fileno())  # 每一行都强制落盘
        time.sleep(1)  # 真·每秒写一次，不会打满CPU
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
