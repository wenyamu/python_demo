## 主配置文件的后缀必须是conf，主配置文件是 supervisord 和 supervisorctl 都要用到的，其引用的配置文件可以是 ini、conf 等
> Supervisor 配置文件通常命名为 supervisord.conf，它被 supervisord 和 supervisorctl 共同使用。如果任一应用程序在启动时未指定选项 -c（该选项用于显式告知应用程序配置文件的名称），应用程序将查找名为 supervisord.conf 的文件。
> 
> https://supervisord.org/configuration.html?highlight=Configuration
> 
> 我就遇到过把主配置文件生成为 echo_supervisord_conf > /etc/supervisor/supervisord.ini，我启动时用 -c 指定了此配置文件，但是在我使用 supervisorctl 命令时，直接提示错误，必须指定配置文件才行。
```
root@orangepizero3:~# supervisorctl status
http://localhost:9001 refused connection
root@orangepizero3:~# supervisorctl -c /etc/supervisor/supervisord.ini status
Multi-resolution                 RUNNING   pid 1945, uptime 0:00:06
state_broadcaster                RUNNING   pid 1469, uptime 0:38:01

```
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
files = /etc/supervisor/my_config/*.conf
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


