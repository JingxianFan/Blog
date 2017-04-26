#!/user/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Jingxian Fan'

'''
async web application
'''
import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

def index(request):
	return web.Response(body = b'<h1>Awesome!</h1>', content_type = 'text/html')


@asyncio.coroutine
def init(loop):
	app = web.Application(loop = loop)
	# bind url with GET / with index
	app.router.add_route('GET', '/', index)
	# create server with aiohttp's TCP
	srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	logging.info('Server started at http://127.0.0.1:9000...')
	return srv

loop = asyncio.get_event_loop()		# 获取EventLoop
loop.run_until_complete(init(loop)) 	# 执行coroutine
loop.run_forever()