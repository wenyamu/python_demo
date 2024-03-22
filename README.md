
python flask gunicorn supervisor 演示文件

搞懂 flask gunicorn supervisor 的作用和关系

### 各文件的功能说明

flasktest.py 是web程序文件，web页面的一些功能代码。

gconf80.py 是作为启动 gunicorn 的配置文件，对 gunicorn 的监听端口，线程数等参数进行设置。

flask80.conf 是作为 supervisor 管理的子进程 gunicorn 的子配置文件，是 supervisor 对 gunicorn 进程的一些管理。

supervisor_flaskapp.conf 是作为启动 supervisor 时的主配置文件，主配置文件中会引入 flask80.conf 子配置文件。
