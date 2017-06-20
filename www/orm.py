#!/user/bin
# -*- coding: utf-8 -*-

__author__ = 'Jingxian Fan'

import asyncio, logging
import aiomysql

'''
选择MySQL作为网站的后台数据库
 
执行SQL语句进行操作，并将常用的SELECT、INSERT等语句进行函数封装
 
在异步框架的基础上，采用aiomysql作为数据库的异步IO驱动
 
将数据库中表的操作，映射成一个类的操作，也就是数据库表的一行映射成一个对象(ORM)
 
整个ORM也是异步操作
 
预备知识：Python协程和异步IO(yield from的使用)、SQL数据库操作、元类、面向对象知识、Python语法
 
# -*- -----  思路  ----- -*-
    如何定义一个user类，这个类和数据库中的表User构成映射关系，二者应该关联起来，user可以操作表User
     
    通过Field类将user类的属性映射到User表的列中，其中每一列的字段又有自己的一些属性，包括数据类型，列名，主键和默认值
 
'''
@asyncio.coroutine
def destory_pool(): #销毁连接池
    global __pool
    if __pool is not None:
        __pool.close()
        yield from  __pool.wait_closed()
        
 # 打印SQL查询语句
def log(sql, args=()):
	logging.info('SQL: %s' % sql)

@asyncio.coroutine
def create_pool(loop, **kw):
	logging.info('create database connection pool...')
	global __pool
	__pool = yield from aiomysql.create_pool(
		host = kw.get('host', 'localhost'),
		port = kw.get('port', 3306),
		user = kw['user'],
		password = kw['password'],
		db = kw['db'],
		charset = kw.get('charset', 'utf8'),
		autocommit = kw.get('autocommit', True),
		maxsize = kw.get('maxsize', 10),
		minsize = kw.get('minsize', 1),
		loop = loop
		)


@asyncio.coroutine
def select(sql, args, size = None):
	log(sql, args)
	global __pool
	with (yield from __pool) as conn:
		cur = yield from conn.cursor(aiomysql.DictCursor)
		yield from cur.execute(sql.replace('?', '%s'), args or ())
		if size:
			rs = yield from cur.fetchmany(size)
		else:
			rs = yield from cur.fetchall()
		yield from cur.close() # 记得关闭cur
		logging.info('rows return: %s' % len(rs) )
		return rs

@asyncio.coroutine
def execute(sql, args):
	log(sql, args)
	global __pool
	with (yield from __pool) as conn:
		try:
			# execute类型的三种SQL操作返回的只有行号，不用DictCursor
			cur = yield from conn.cursor()
			yield from cur.execute(sql.replace('?', '%s'), args)
			affected = cur.rowcount
			yield from cur.close()
		except BaseException as e:
			# # rollback() in case there was error
			# if not autocommit:
			# 	yield from conn.rollback()
			raise
		finally:
			conn.close()
		return affected

# 根据输入的参数生成占位符列表
def create_args_string(num):
	L = []
	for n in range(num):
		L.append('?')
	# 以‘，’为分隔符， 将列表合成为字符串
	return (', '.join(L))

# 定义Field类， 负责保存数据库表的字段名和字段类型
class Field(object):
	# 表的字段包含了名字，类型，是否为表的主键和默认值
	def __init__(self, name, column_type, primary_key, default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	# 当打印数据库表时， 输出数据库表的信息：类名，字段类型和名字
	def __str__(self):
		return ('<%s, %s, %s>' %(self.__class__.__name__, self.column_type, self.name))

# 定义不同类型的衍生Field
# 表的不同列的字段类型不一样

class StringField(Field):
	def __init__(self, name = None, primary_key = False, default = None, column_type = 'varchar(100)'):
		super().__init__(name, column_type, primary_key, default)

class BooleanField(Field):
	def __init__(self, name = None, default = None):
		super().__init__(name, 'boolean', False, default)

class IntegerField(Field):
	def __init__(self, name = None, primary_key = False, default = 0):
		super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):
	def __init__(self, name = None, primary_key = False, default=0.0):
		super().__init__(name, 'real', primary_key, default)

class TextField(Field):
	def __init__(self, name = None, default = None):
		super().__init__(name, 'Text', False, default)

		
# 定义Model的元类
# 所有的元类都继承自type
# ModelMetaclass元类定义了所有Model基类(继承ModelMetaclass)的子类实现的操作

# ModelMetaclass的工作主要是为一个数据库表映射成一个封装的类做准备
# 读取具体子类(如User)的信息
# 创造类的时候，排除对Model的修改
# 在当前类中查找所有类属性attrs， 如果找到Field属性就将其保存到__mappings__的dict中
# 将数据库表名保存到__table__中

# 完成以上工作就可以在Model中定义各种数据库的操作方法


class ModelMetaclass(type):
	# __new__控制__init__的执行，所以在其执行之前
	# cls: 代表了__init__的类，此参数在实例化时由python解释器自动提供 如User和Model
	# bases: 代表继承父类的集合
	# attrs: 类的方法集合

	def __new__(cls, name, bases, attrs):

		# 排除Model
		if name == 'Model':
			return type.__new__(cls, name, bases, attrs)

		# 获取table名词
		tableName = attrs.get('__table__', None) or name
		logging.info('found model: %s (table: %s)' %(name, tableName))

		# 获取Field和主键名
		mappings = dict()
		Fields = []
		primaryKey = None
		for k, v in attrs.items():
			if isinstance(v, Field):
				# 此处打印的k是类的一个属性；v是这个属性在数据库中对应的Field列表属性
				logging.info('	found mapping: %s --> %s' %(k, v))
				mappings[k] = v

				if v.primary_key:
					if primaryKey:
						raise StandardError('Duplicate primary key for field: %s' % k)
					primaryKey = k
				else:
					Fields.append(k)

		if not primaryKey:
			raise StandardError('Primary Key is not found')

		# 从类属性中删除Field属性
		for k in mappings.keys():
			attrs.pop(k)

		# 保存除主键外的属性名为`` (运算出字符串) 列表形式
		escaped_fields = list(map(lambda f: '`%s`' %f, Fields))

		# 保存属性和列的映射关系
		attrs['__mappings__'] = mappings
		# 保存表名
		attrs['__table__'] = tableName
		# 保存主键属性名
		attrs['__primary_key__'] = primaryKey
		# 保存除主键外的属性名
		attrs['__fields__'] = Fields

		# 构造默认的SELECT, INSERT, UPDATE, DELETE语句
		# `` 反引号的功能同repr() ：创建一个字符串显示用 供解释器读取用
		# 即获取对象的可打印的表现形式

		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
		attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values(%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
		attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), Fields)), primaryKey)
		attrs['__delete__'] = 'delete from `%s` where `%s` = ?' % (tableName, primaryKey)
		return type.__new__(cls, name, bases, attrs)






# 定义ORM所有映射的基类： Model
# Model类的任意子类可以映射一个数据库表
# Model类可以看做是对所有数据库表操作的基本定义的映射

# 基于字典查询形式，从dict继承，拥有字典所有功能，同时实现特殊方法__getattr__和__setattr__，能够实现属性操作
# 实现数据库操作的所有方法，定义为class方法，所有继承自model都具有数据库操作方法

class Model(dict, metaclass=ModelMetaclass):
	def __init__(self, **kw):
		super(Model, self).__init__(**kw)

	def __getattr__(self, key):
		try:
			return self[key]
		except:
			raise AttributeError(r'"Model" object has no attribute: %s' % key)

	def __setattr__(self, key, value):
		self[key] = value

	def getValue(self, key):
		# 内建函数getattr会自动处理
		return getattr(self, key, None)

	def getValueOrDefault(self, key):
		value = getattr(self, key, None)
		if not value:
			field = self.__mappings__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.info('using default value for %s: %s' % (key, str(value)))
				setattr(self, key, value)
		return value


	@classmethod
	# 类方法有类变量cls传入，从而可以用cls做一些相关处理，并且有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类
	@asyncio.coroutine
	def findAll(cls, where=None, args=None, **kw):
		'''find objects by where clause'''
		sql = [cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)

		if args is None:
			args = []

		orderBy = kw.get('orderBy', None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)

		limit = kw.get('limit', None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit, int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit, tuple) and len(limit) == 2:
				sql.append('?, ?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value: %s' % str(limit))
		rs = yield from select(' '.join(sql), args)
		return [cls(**r) for r in rs]
	@classmethod
	@asyncio.coroutine
	def findNumber(cls, selectField, where=None, args=None):
		' find number by select and where. '
		sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs = yield from select(' '.join(sql), args, 1)
		if len(rs) == 0:
			return None
		return rs[0]['_num_']
	@classmethod
	@asyncio.coroutine
	def find(cls, pk):
		' find object by primary key. '
		rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
		if len(rs) == 0:
			return None
		return cls(**rs[0])

	@asyncio.coroutine
	def save(self):
		args = list(map(self.getValueOrDefault, self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows = yield from execute(self.__insert__, args)
		if rows != 1:
			logging.warn('failed to insert record: affected rows: %s' % rows)
	@asyncio.coroutine
	def update(self):
		args = list(map(self.getValue, self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		rows = yield from execute(self.__update__, args)
		if rows != 1:
			logging.warn('failed to update by primary key: affected rows: %s' % rows)
	@asyncio.coroutine
	def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = yield from execute(self.__delete__, args)
		if rows != 1:
			logging.warn('failed to remove by primary key: affected rows: %s' % rows)





