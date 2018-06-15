#!/usr/bin/env python
# -*-coding:utf-8-*-
# @File  : oracle.py
# @Author: shenwc
# @modify: sunml
# @Date  : 2018/4/12
# @Desc  : oracle 数据库访问

import cx_Oracle
##cx_Oracle中文支持
import os
os.environ['NLS_LANG'] = 'SIMPLIFIED CHINESE_CHINA.UTF8'

class Oracle:
    def __init__(self,username,password,serverName): 
        self.dbconn = cx_Oracle.connect(username+'/'+password+'@'+serverName)
        self.cursor = self.dbconn.cursor()

    # 关闭连接
    def closedb(self):
        self.cursor.close()
        self.dbconn.close()

    # 关闭连接
    def close(self):
        self.commit()
        self.cursor.close()
        self.dbconn.close()

    # 查询表的所有列
    def columns(self, table,args={}):
        sql = "SELECT * FROM %s WHERE 1=2" %table
        self.execute(sql, args)
        return  [r[0].lower() for r in self.cursor.description]
        
    #通过sql获取列名称
    def columns_sql(self,sql,args={}):
        self.execute(sql, args)
        return  [r[0].lower() for r in self.cursor.description]

    # 根据表自动创建参数字典
    def create_params(self, table, args={}):
        col_list = self.columns(table)
        params = {}
        for k in col_list:
            if args.has_key(k):
                params[k] = args[k]
        return params

    # 执行sql
    def execute(self, sql, args={}):
        try:
            return self.cursor.execute(sql, args)
        except Exception as e:
            self.close()
            raise e

    # 批量执行
    def executemany(self, sql, args):
        try:
            return self.cursor.executemany(sql, args)
        except Exception as e:
            self.close()
            raise e

    # 备份记录,如果没有该表格将自动建表，以log_表名 命名,参数二：操作人工号，参数三：操作说明，
    # 参数四：用于where条件，如 where 字段3=值3 and 字段4=值4，格式{'字段3':'值3','字段4':'值4'}
    def backup(self, table, userid, remark, cond_dict):
        cond_dict = self.create_params(table, cond_dict)
        sql = ["select count(*)cnt FROM user_tables "]
        sql.append(" WHERE table_name = upper('log_%(table)s')")
        rows = self.query("".join(sql) % locals())
        if rows[0]["cnt"] == 0:  # 注意oracle列名大写
            self.execute("create table log_%(table)s as  select * from %(table)s where 1>2 " % locals())
            self.execute(" alter table log_%(table)s add(backup_userid varchar2(40),"
                         "backup_date date,back_remark varchar2(200))" % locals())
        cond_stmt = ' and '.join(['%s=:%s' % (k, k) for k in cond_dict.keys()])
        upd_sql = "insert into log_%(table)s select t.*,:userid,sysdate,:remark " \
                  "from %(table)s t where %(cond_stmt)s"
        cond_dict['userid'] = userid
        cond_dict['remark'] = remark
        return self.execute(upd_sql % locals(), cond_dict)

    # 执行sql，参数一：sql语句，参数二：参数字典{'字段1'：'值1','字段2':'值2'}
    def query(self, sql, args={}):
        self.execute(sql, args)
        return self.get_rows()

    #通过表名称查询所有字段列数据
    def query_table(self, table,args={}): 
        self.execute("SELECT * FROM %s" %table, args)
        return self.get_rows()

    # 分页查询，参数一：sql语句，参数二：参数字典{'字段1'：'值1','字段2':'值2'}，参数三：页码，参数四：分页大小
    def query_pages(self, sql, args={}, page=1, page_size=30):
        _args, count_args = args, args
        page = int(page)
        # print "page:%s" %(page,)
        # 下一页
        next_page = page_size * page
        # 当前页
        cur_page = page_size * (page - 1)
        if page == 1 or cur_page < 0:
            cur_page = 0
            next_page = page_size
        sql = """SELECT * FROM(
            SELECT ROWNUM RN,T.* FROM(""" + sql + """)T
            WHERE ROWNUM<=:next_page
            )WHERE RN >=:cur_page """
        count_sql = """
            SELECT COUNT(1)CNT FROM (""" + sql + """)"""
        _args["cur_page"] = cur_page
        _args["next_page"] = next_page
        rows = self.query(sql, _args)
        countrows = self.query(count_sql, count_args)
        return rows, countrows[0]['cnt']

    # oracle的参数名必须使用:代替，如 userid = :userid
    def insert(self, table, column_dict):
        column_dict = self.create_params(table, column_dict)
        keys = ','.join(column_dict.keys())
        values = column_dict.values()
        placeholder = ','.join([':%s' % (v) for v in column_dict.keys()])
        ins_sql = 'INSERT INTO %(table)s (%(keys)s) VALUES (%(placeholder)s)'
        self.execute(ins_sql % locals(), column_dict)

    # 获取序列的下一个值，传入sequence的名称
    def nextval(self, seq):
        self.cursor.execute("SELECT %(seq)s.nextval from dual " % locals())
        result = self.cursor.fetchall()
        return result[0][0]

    # 批量插入数据库，参数一：表名，参数二：['字段1','字段2',...],参数二：[('值1','值2',...),('值1','值2',...)]
    def multi_insert(self, table, columns=[], values=()):
        keys = ','.join(columns)
        placeholder = ','.join([':%s' % (v) for v in columns])
        sql = 'INSERT INTO %(table)s (%(keys)s) VALUES(%(placeholder)s)'
        return self.cursor.executemany(sql % locals(), values)

    # 更新，参数一：表名，参数二用于set 字段1=值1，字段2=值2...格式：{'字段1':'值1','字段2':'值2'},
    # 参数三：用于where条件，如 where 字段3=值3 and 字段4=值4，格式{'字段3':'值3','字段4':'值4'}
    def update(self, table, column_dict={}, cond_dict={}):
        column_dict = self.create_params(table, column_dict)
        cond_dict = self.create_params(table, cond_dict)
        set_stmt = ','.join(['%s=:%s' % (k, k) for k in column_dict.keys()])
        cond_stmt = ' and '.join(['%s=:%s' % (k, k) for k in cond_dict.keys()])
        upd_sql = 'UPDATE %(table)s set %(set_stmt)s where %(cond_stmt)s'
        args = dict(column_dict, **cond_dict)  # 合并成1个
        return self.execute(upd_sql % locals(), args)

    # 删除，参数一：表名，#参数二：用于where条件，如 where 字段3=值3 and 字段4=值4，格式{'字段3':'值3','字段4':'值4'}
    def delete(self, table, cond_dict):
        cond_dict = self.create_params(table, cond_dict)
        cond_stmt = ' and '.join(['%s=:%s' % (k, k) for k in cond_dict.keys()])
        del_sql = 'DELETE FROM %(table)s where %(cond_stmt)s'
        return self.execute(del_sql % locals(), cond_dict)

    # 提取数据，参数一提取的记录数，参数二，是否以字典方式提取。为true时返回：{'字段1':'值1','字段2':'值2'}
    def get_rows(self, size=None, is_dict=True):
        if size is None:
            rows = self.cursor.fetchall()
        else:
            rows = self.cursor.fetchmany(size)
        if rows is None:
            rows = []
        if is_dict:
            dict_rows = []
            dict_keys = [r[0].lower() for r in self.cursor.description]
            for row in rows:
                dict_rows.append(dict(zip(dict_keys, row)))
            rows = dict_rows
        return rows

    # 获取记录数
    def get_rows_num(self,sql):
        self.cursor.execute(sql)
        self.cursor.fetchall()
        return self.cursor.rowcount

    # 提交
    def commit(self):
        self.dbconn.commit()

    # 回滚
    def rollback(self):
        self.dbconn.rollback();

if __name__ == "__main__":
    # 连接数据库
    db = Oracle('ibillapp', 'Sitech2018', 'HOTDB')
    columns=db.columns('t_pp_prod_index')

    print(columns)
    #ret = deal_db.query("select 'gaga' from dual")
    #print(ret)





