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
### 配置程序
```
mkdir -p /etc/supervisor/my_config && \
cat > /etc/supervisor/my_config/time_app.conf <<EOF
[program:1-time_app]
;标准推荐范围为 0-999 ‌默认值‌：‌999‌ ‌规则‌：‌数值越小，优先级越高，越先启动‌。
; priority=11
;创建该项目用户
user = root

;应用目录，存放目录 /etc/supervisor
directory = /etc/supervisor

;程序命令
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
