from flask import Flask, render_template, url_for, request, send_from_directory, send_file
import pymysql
import os

app = Flask(__name__,
      template_folder='/python/templates',
      static_folder='/python/asset',#文件在磁盘上的实际存放位置
      static_url_path=None,#相当于一个路由
      # static_url_path="/abc",#相当于一个路由 @app.route('/abc')
      )

'''
# __name__ 本文件的文件名（不含后缀）

# template_folder 存放模板的目录，缺省值为当前项目目录下的templates目录

# static_folder 存放静态文件的目录，缺省值为当前项目目录下的 static 目录

# static_url_path 访问静态文件的路由设置，配合 static_folder 使用

一句话区分
‌static_folder = 磁盘上的物理位置‌：服务器上那个‌真实存在‌的文件夹路径（文件到底躺在哪）。
‌static_url_path = 网址上的访问前缀‌：浏览器地址栏里‌用什么路径‌能访问到它（对外暴露的入口）。
一个是"库房在哪"，一个是"门店开在哪条街"。两者互相独立，可以随便搭配。
这两个参数是一对"‌一个管磁盘、一个管网址‌"的组合，很多人一开始就混在这儿。先把它们拆开看：

app = Flask(__name__, static_folder='/python/asset', static_url_path='/')
凡是不带前缀的网址(static_url_path='/')，都去 /python/asset 目录里找文件‌。

http://ip:5000/monitor.html → 读 /python/asset/monitor.html

app = Flask(__name__, static_folder='/python/asset', static_url_path='/abc')
凡是带前缀的网址(static_url_path='/abc')，都去 /python/asset 目录里找文件‌。

http://ip:5000/abc/monitor.html → 读 /python/asset/monitor.html
'''

@app.route('/webrtc-player1')
def index_webrtc1():
    # 页面文件 webrtc-player1.html 我是放在与本py文件同级的 html 目录中
    directory = os.path.join(os.getcwd(), 'html') 
    filename = 'webrtc-player1.html'
    return send_from_directory(directory, filename)
    
@app.route('/webrtc-player2')
def index_webrtc2():
    return send_file('/python/html/webrtc-player2.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory("/python/html", filename)

@app.route('/')
def index_a():
    return send_file('/python/html/index.html')

@app.route("/temp")
def index_b():
  data = [{"name":"menghuiguli","age":"28"},{"name":"lisi","age":"22"},{"name":"wangwu","age":"40"},{"name":"zhaoliu","age":"18"}]
  return render_template("page.html",data=data)

@app.route("/url_for")
def url_for_a():
  #return request.args['name']
  #return request.url +"<br/>"+ request.base_url +"<br/>"+ request.host_url+"<br/>"+request.host+"<br/>"+request.path+"<br/>"+request.full_path+"<br/>"+request.url_root
  #return url_for('index_b')
  return url_for('index_b', next='a', nexta='aa')+"<br/>"+url_for('index_b')+"<br/>"+url_for('pym222', home_id='a', nexta='aa')

@app.route("/pym2/<home_id>")
def pym222(home_id):
  # 1. 查询数据库
  # 1.1 创建Connection连接
  conn = pymysql.connect(
    host='1.2.3.4', 
    port=3306, 
    database='123', 
    user='abc', 
    password='xxx', 
    charset='utf8', 
    cursorclass = pymysql.cursors.DictCursor # 返回json
    )
  # 1.2 获得Cursor对象
  cur = conn.cursor()
  # 1.3 构造参数列表
  params = [home_id]
  # 1.4 执行select语句，查询数据
  cur.execute('select id,name,home from student where home=%s', params)
  #cur.execute('select id,name,home from student')
  # 1.5 获取查询的结果
  result = cur.fetchone() # {}
  #result = cur.fetchall() # [{}]
  #print(result)
  # 1.6 关闭Cursor对象
  cur.close()
  # 1.7 闭Connection对象
  conn.close()

  # 2. 模板渲染
  return render_template(
    "page.html", 
    xxx=result,
    **result
    )

@app.route('/ccc')
def test():
  context = {
    'title_name':"test_render",
    'name2':"sp4rk",
    'test_variable':"It works"
  }
  return render_template('page.html', **context)

@app.route("/pym/<home_id>")
def pym(home_id):
  # 1. 查询数据库
  # 1.1 创建Connection连接
  conn = pymysql.connect(
    host='1.2.3.4', 
    port=3306, 
    database='123', 
    user='abc', 
    password='xxx', 
    charset='utf8', 
    #cursorclass = pymysql.cursors.DictCursor # 返回json
    )
  # 1.2 获得Cursor对象
  cur = conn.cursor()
  # 1.3 构造参数列表
  params = [home_id]
  # 1.4 执行select语句，查询数据
  cur.execute('select id,name,home from student where home=%s', params)
  #cur.execute('select id,name,home from student')
  # 1.5 获取查询的结果
  #result = cur.fetchone() # {}
  result = cur.fetchall() # [{}]
  #print(result)
  # 1.6 关闭Cursor对象
  cur.close()
  # 1.7 闭Connection对象
  conn.close()

  # 2. 模板渲染
  return render_template(
    "page.html",
    xxx=result,
    testdata=result
    )

abc = "abc123"
efg = "efg456"
@app.route('/abc')
def index1():
  return __name__ + abc + efg

uname = "10000"
@app.route('/index')
def index2():
  return render_template('page.html', title='tttt',username=uname)
  #return 'Hi! render_template'

@app.route('/index/<int:uid>')
def index3(uid):
  return render_template('page.html', username=uid)
  #return 'Hi! render_template'

@app.route('/user/<u_id>')
def user_info(u_id):
  return {
    "msg": "success",
    "data": {
      "id": u_id,
      "username": 'yuz',
      "age": 18
    }
  }

#以下命令，只有在使用 python this.py 才起作用
if __name__=='__main__':
  app.run(debug=True,host='0.0.0.0',port=5000)
