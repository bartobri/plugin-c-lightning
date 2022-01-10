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

	peers = plugin.rpc.listpeers()

	if ('peers' not in peers):
		return reply

	for p in peers['peers']:

		if ('channels' not in p):
			continue

		for c in p['channels']:

			if 'short_channel_id' in c and c['state'] == 'CHANNELD_NORMAL':
				scid = c['short_channel_id']
				ours = c['spendable_msatoshi']
				theirs = c['receivable_msatoshi']

				our_pct = int((ours / (ours + theirs)) * 100)

				base = c['fee_base_msat']
				ppm = c['fee_proportional_millionths']

				if (our_pct >= 95):
					ppm = 0
				elif (our_pct >= 85):
					ppm = 1
				elif (our_pct >= 75):
					ppm = 2
				elif (our_pct >= 25):
					ppm = 5
				elif (our_pct >= 15):
					ppm = 10
				elif (our_pct >= 5):
					ppm = 11
				else:
					ppm = 12

				if (base != c['fee_base_msat'] or ppm != c['fee_proportional_millionths']):

					plugin.rpc.setchannelfee(scid, base, ppm)

					reply[scid] = {}
					reply[scid]['ours'] = ours
					reply[scid]['theirs'] = theirs
					reply[scid]['our_pct'] = our_pct
					reply[scid]['base'] = base
					reply[scid]['ppm'] = ppm

	return reply


@plugin.init()
def init(options, configuration, plugin):
    plugin.log("Plugin brian.py initialized")

plugin.run()