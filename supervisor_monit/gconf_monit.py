#gconf_monit.py

from gevent import monkey
monkey.patch_all()
import multiprocessing

# 指定应用所在的目录，不然就要使用下面的方式运行
chdir = "/python/supervisor_monit"

'''
# 当未指定 chdir 时，需要先进入 monit.py 所在的目录，不然会出现错误提示
# ModuleNotFoundError: No module named 'monit'

cd /python/supervisor_monit
gunicorn -c /xxx/gconf_monit.py monit:app --preload
'''

# 注意：True, False 必须首字母大写

#debug = True # 调试模式运行
daemon = False # Gunicorn 守护进程，默认False(即不让其在后台运行，而是使用supervisor管理进程)
# True，表示代码更新时将被热载入（不用手动重启进程了）。如果是直接运行gunicorn命令，直接加参数 --reload 即可
reload = True
#绑定与Nginx通信的端口ipv4、ipv6
bind = '0.0.0.0:5000'
#bind = '[::]:5000'
#workers = multiprocessing.cpu_count() # 根据计算的CPU数量设置进程数
workers = 1
threads = 1 #指定每个进程开启的线程数
#默认为sync阻塞模式，最好选择gevent模式，需要安装gevent模块
#Flask+gevent高效部署（基于gevent模块实现并发）：适用于io访问频繁的项目(比如对数据库的读写, 发送Http请求等等)，算法类型不适用
worker_class = 'gevent'

#设置环境变量(key=value)，将变量传递给flask
'''
# flask.py 中调用变量
import os
os.getenv('ljs1')
'''
raw_env=["ljs1=111","ljs2=bbb"]

loglevel = 'info' #日志级别，这个日志级别指的是错误日志的级别，而访问日志的级别无法设置
access_log_format = '%(t)s %(p)s %(h)s "%(r)s" %(s)s %(L)s %(b)s %(f)s" "%(a)s"'#设置gunicorn访问日志格式，错误日志无法设置
'''
其每个选项的含义如下：
h  remote address
l  '-'
u  currently '-', may be user name in future releases
t  date of the request
r  status line (e.g. ``GET / HTTP/1.1``)
s  status
b  response length or '-'
f  referer
a  user agent
T  request time in seconds
D  request time in microseconds
L  request time in decimal seconds
p  process ID
'''
accesslog = "/python/logs/gunicorn_access_monit.log" #访问日志文件
errorlog  = "/python/logs/gunicorn_error_monit.log" #错误日志文件

#gconf_monit.py 内容结束