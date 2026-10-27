### 安装及初始化配置
```
apt install -y build-essential python3-dev libevent-dev && \
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
files = /etc/supervisor/my_config/*.ini
EOF
```

### 配置子程序配置项，此配置项不同的程序有不同的设置
```
mkdir -p /etc/supervisor/my_config && \
cat > /etc/supervisor/my_config/Multi_Resolution.conf <<EOF
[program:Multi_Resolution]
;标准推荐范围为 0-999 ‌默认值‌：‌999‌ ‌规则‌：‌数值越小，优先级越高，越先启动‌。
; priority=11
;创建该项目用户
user = root

;应用目录，hls_abr_gen.py 存放目录 /root/test
directory = /root/test

;ffmpeg程序命令
command = python3 hls_abr_gen.py -i rtmp://39.96.29.167:1935/show-flv/abc123456 -o /mnt/hls3 --run

autostart = true ;在supervisord启动的时候，false 表示不自动启动，true 表示随着启动
autorestart = true ;程序异常退出后，false 表示不自动重启，true 表示自动重启
startsecs = 3 ;稳定运行N秒后，从“正在启动”转成“正在运行”状态，值为0表示无需保持运行特定时长。
startretries = 3 ;进程启动失败后，最大尝试的次数。当超过3次后，supervisor将把此进程的状态置为FATAL
stopasgroup = true ;确保关闭supervisord时停止所有相关子进程
killasgroup = true ;确保关闭supervisord时停止所有相关子进程

;日志目录必须事先存在，不然会出错
;stdout_logfile = /tmp/Multi_Resolution_out.log
;stderr_logfile = /tmp/Multi_Resolution_err.log
EOF
```

### 运行
```
TZ=Asia/Shanghai /usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
```


