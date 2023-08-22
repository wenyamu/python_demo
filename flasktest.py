from flask import Flask, render_template, url_for, request
import pymysql
app = Flask(__name__,
      template_folder='/python/templates',
      static_folder='/python/asset',
      static_url_path="/",
      )

# __name__ 本文件的文件名（不含后缀）
# template_folder 存放模板的目录，缺省值为当前项目目录下的templates目录
# static_folder 存放静态文件的目录（注意：存放在此目录下的文件，都会被当成静态文件处理，例如php、py文件），通常存放css/js/jpg/html等文件（假设项目的绝对路径为"/py",如果参数值为"/py/sss"时，可以直接通过xxx.com/sss/x.jpg 进行访问，此时static_folder的值做为存放目录以及url访问），缺省值为当前项目目录下的static目录
# static_url_path 访问静态文件的路由设置，可以配合static_folder使用，例如：当static_url_path参数值为"/aaa"时，可以直接通过xxx.com/aaa/x.jpg 进行访问，此时static_folder的值仅做为存放目录，不作为url访问

@app.route("/url_for")
def url_for_a():
  #return request.args['name']
  return request.url +"<br/>"+ request.base_url +"<br/>"+ request.host_url+"<br/>"+request.host+"<br/>"+request.path+"<br/>"+request.full_path+"<br/>"+request.url_root
  #return url_for('index')
  #return url_for('index_a', next='a', nexta='aa')+"<br/>"+url_for('index')+"<br/>"+url_for('pym222', home_id='a', nexta='aa')

@app.route("/jjj")
def index_a():
  data = [{"name":"menghuiguli","age":"28"},{"name":"lisi","age":"22"},{"name":"wangwu","age":"40"},{"name":"zhaoliu","age":"18"}]
  return render_template("page.html",data=data)
  
@app.route('/')
def index():
  return render_template('index.html', title='python',info="flask web app")

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
