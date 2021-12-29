#!/usr/bin/env python3

"""
Plugin Descr Here
"""

import pyln.client
import json

plugin = pyln.client.Plugin()

@plugin.method("brian")
def brian(plugin):

	""" Function Descr Here """

	reply = {}
	reply['gar'] = 1;

	return reply


@plugin.init()
def init(options, configuration, plugin):
    plugin.log("Plugin brian.py initialized")

plugin.run()