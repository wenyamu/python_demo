#!/usr/bin/env python3
# coding: utf-8
import os
import xlwt
import pymysql
import datetime

class MysqlToExcel():
    def __init__(self):
        self.host      = 'bdm721903285.my3w.com'
        self.port      = 3306
        self.user      = 'bdm721903285'
        self.passwd    = 'Bdm721903285'
        self.db_name   = 'bdm721903285_db'
        self.file_name = 'toexcel.xls' #生成的excel表格，支持xls、xlsx

    def get_query_results(self):
        sql = "select * from student"

        conn = pymysql.connect(
            host        = self.host,
            user        = self.user,
            passwd      = self.passwd,
            port        = self.port,
            database    = self.db_name,
            charset     = 'utf8',
            cursorclass = pymysql.cursors.DictCursor
        )
        cur = conn.cursor()  # 创建游标
        cur.execute(sql)  # 执行sql命令
        result = cur.fetchall()  # 获取执行的返回结果
        # print(result)
        cur.close()
        conn.close()  # 关闭mysql 连接
        return result

    def generate_table(self):
        """
        生成excel表格
        """
        # 删除已存在的文件
        #if  os.path.exists(self.file_name):
        #    os.remove(self.file_name)

        result = self.get_query_results()
        #print(result) # [{'id': 62, 'name': '张三1', 'sex': '男', 'minzu': '汉', 'danwei': '武汉1', 'phone': '13812345678', 'home': '119'},{...}]
        if  not result:
            print("查询结果为空")
            return False

        # 创建excel对象
        wb = xlwt.Workbook()
        sheetname = wb.add_sheet('Sheet1', cell_overwrite_ok = True)

        # 列字段(导出的excel中显示)
        column_names = ['序号','姓名','性别','民族','单位','时间']

        # 写第一行（写入列字段）
        for i in range(0, len(column_names)):
            sheetname.write(0, i, column_names[i])

        # 写入多行
        num = 1  # 计数器
        for j in result:
            sheetname.write(num, 0, j['id']) # 从第2行，第1列，写入json[0]['id']
            sheetname.write(num, 1, j['name'])
            sheetname.write(num, 2, j['sex'])
            sheetname.write(num, 3, j['minzu'])
            sheetname.write(num, 4, j['danwei'])
            # 日期转换为字符串（不然导出到excel中显示不出具体时间）
            time_str = j['date_time'].strftime('%Y-%m-%d %H:%M:%S')
            sheetname.write(num, 5, time_str)

            num += 1  # 自增1

        # 保存文件
        wb.save(self.file_name)

        # 判断文件是否存在
        if  not os.path.exists(self.file_name):
            print("生成excel失败")
            return False

        print("生成excel成功")
        return True

if __name__ == '__main__':
    MysqlToExcel().generate_table()
