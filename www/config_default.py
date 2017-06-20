#!/usr/bin/env python3.5
# -*- coding: utf-8 -*-

'''
Default configuration
'''

__author__ = 'Jingxian Fan'

configs = {
	'debug': True,
	'db': {
		'host': '127.0.0.1',
		'port': 3306,
		'user': 'root',
		'password': 'guaiyidian',
		'db': 'Blog'
	},
	'session': {
		'secret':'Blog'
	}
}