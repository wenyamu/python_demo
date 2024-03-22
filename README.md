
python flask gunicorn supervisor 演示文件

搞懂 flask gunicorn supervisor 的作用和关系

gconf80.py 是作为启动 gunicorn 时的配置文件

flask80.conf 是作为 supervisor 管理的子进程 gunicorn 的入口文件

supervisor_flaskapp.conf 是作为启动 supervisor 时的主配置文件
