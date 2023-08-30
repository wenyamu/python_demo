import xlrd
import pymysql
#打开数据所在的工作簿mysql.xls（xlrd只能读取xls格式），以及选择存有数据的工作表Sheet1(注意区分大小写)
book = xlrd.open_workbook("student.xls")
sheet = book.sheet_by_name("Sheet1")
#建立一个MySQL连接
conn = pymysql.connect(
    host    = 'xxx.yyy.com',
    port    = 3306,
    user    = 'xxx',
    passwd  = 'XXX',
    db      = 'xxx_db',
    charset = 'utf8'
    )
# 获得游标
cur = conn.cursor()
# 创建插入SQL语句
query = 'insert into student (name,sex,minzu,danwei,phone,home,date_time) values (%s, %s, %s, %s, %s, %s, %s)'
# 创建一个for循环迭代读取xls文件每行数据的
for r in range(1, sheet.nrows): #从第2行开始是要跳过标题行
    n  = sheet.cell(r,1).value #从第2行，第2列（单元格B2）开始
    s  = sheet.cell(r,2).value
    m  = sheet.cell(r,3).value
    d  = sheet.cell(r,4).value
    p  = sheet.cell(r,5).value
    h  = sheet.cell(r,6).value
    t  = sheet.cell(r,7).value
    vs = (n,s,m,d,p,h,t)
    # 执行sql语句
    cur.execute(query, vs)
cur.close()
conn.commit()
conn.close()
columns = str(sheet.ncols)
rows    = str(sheet.nrows)
print ("已导入 "+columns+" 列 "+rows+" 行数据到MySQL数据库!")
