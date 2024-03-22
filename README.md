
python flask gunicorn supervisor 演示文件

搞懂 flask gunicorn supervisor 的作用和关系

### 各文件的功能说明

flasktest.py 是web程序文件，是用 python 写的 web 页的功能代码。类似于 php 写的 web 页 xxx.php 文件是一个意思。

gconf80.py 是作为启动 gunicorn 的配置文件，对 gunicorn 的监听端口，线程数等参数进行设置。

flask80.conf 是作为 supervisor 管理的子进程的配置文件，对 gunicorn 进程的一些管理。gunicorn 就是用来启动 flask web 程序的，示例如下。
```bash
[program:flask_app80]
...
...
command = /usr/local/bin/gunicorn -c /python/gconf80.py flasktest:app
autostart = true #在supervisord启动的时候也自动启动
...
...
```
supervisor_flaskapp.conf 是作为启动 supervisor 时的主配置文件，主配置文件中会引入 flask80.conf 子配置文件。
