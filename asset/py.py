from flask import Flask, render_template
import pymysql
app = Flask(__name__, template_folder='templates')

@app.route("/pym/<home_id>")
def pym(home_id):
    # 1. 查询数据库
    # 1.1 创建Connection连接
    conn = pymysql.connect(host='bdm721903285.my3w.com', port=3306, database='bdm721903285_db', user='bdm721903285', password='Bdm721903285', charset='utf8')
    # 1.2 获得Cursor对象
    cs1 = conn.cursor()
    # 1.3 构造参数列表
    params = [home_id]
    # 1.4 执行select语句，并返回受影响的行数：查询所有数据
    cs1.execute('select * from student where home=%s', params)
    # 1.5 获取查询的结果
    result = cs1.fetchone()
    # result = cs1.fetchall()
    print(result)
    # 1.6 关闭Cursor对象
    cs1.close()
    # 1.7 闭Connection对象
    conn.close()

    # 2. 模板渲染
    return render_template("index.html", xxx=home_id)

@app.route('/')
def index1():
    return "456"

uname = "10000"
@app.route('/index')
def index2():
    return render_template('index.html', title='tttt',username=uname)
    #return 'Hi! render_template'

@app.route('/index/<int:uid>')
def index3(uid):
    return render_template('index.html', username=uid)
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

#如果使用 gunicorn -w 4 -b 0.0.0.0:5000 flasktest:app 以下命令不起作用
if __name__=='__main__':
    app.run(debug=True,host='0.0.0.0',port=5000)
