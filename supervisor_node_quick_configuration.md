
```
apt install -y build-essential python3-dev libevent-dev && \
python3 -m pip install supervisor && \
mkdir -p /etc/supervisor && \
echo_supervisord_conf > /etc/supervisor/supervisord.ini && \
cp /etc/supervisor/supervisord.ini /etc/supervisor/supervisord.ini.bak && \
grep -Ev '^\s*[;#]' /etc/supervisor/supervisord.ini.bak > /etc/supervisor/supervisord.ini
```

cat >> /etc/supervisor/supervisord.ini <<EOF
#web管理界面
[inet_http_server]
port = 0.0.0.0:8000
username = admin
password = admin
[include]
files = /etc/supervisor/my_config/*.ini
EOF
```
mkdir -p /etc/supervisor/my_config && \
cat > /etc/supervisor/my_config/ffmpeg.ini <<EOF
[program:push_mediamtx]
;标准推荐范围为 0-999 ‌默认值‌：‌999‌ ‌规则‌：‌数值越小，优先级越高，越先启动‌。
; priority=11
;创建该项目用户
user = root

;应用目录
directory = /root/test

;ffmpeg程序命令
command = rm -rf /mnt/hls3 && mkdir -p /mnt/hls3 && python3 hls_abr_gen.py -i rtmp://39.96.29.167:1935/show-flv/abc123456 -o /mnt/hls3 --run

autostart = false ;在supervisord启动的时候，false 表示不自动启动，true 表示随着启动
autorestart = true ;程序异常退出后，false 表示不自动重启，true 表示自动重启
startsecs = 3 ;稳定运行N秒后，从“正在启动”转成“正在运行”状态，值为0表示无需保持运行特定时长。
startretries = 3 ;进程启动失败后，最大尝试的次数。当超过3次后，supervisor将把此进程的状态置为FATAL
stopasgroup = true ;确保关闭supervisord时停止所有相关子进程
killasgroup = true ;确保关闭supervisord时停止所有相关子进程

;日志目录必须事先存在，不然会出错
;stdout_logfile = /python/logs/push_mediamtx_out.log
;stderr_logfile = /python/logs/push_mediamtx_err.log
EOF
```
