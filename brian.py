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
	## needs_balance = {}
	needs_drain = {}
	needs_fill = {}

	peers = plugin.rpc.listpeers()
	for p in peers['peers']:
		for c in p['channels']:
			if 'short_channel_id' in c and c['state'] == 'CHANNELD_NORMAL':
				scid = c['short_channel_id']
				ours = c['spendable_msatoshi']
				theirs = c['receivable_msatoshi']

				mid = ((ours + theirs) / 2)
				quarter = mid / 2
				high_thresh = mid + quarter
				low_thresh = mid - quarter

				if (ours >= high_thresh):
					needs_drain[scid] = int(ours - mid)
				elif (ours <= low_thresh):
					needs_fill[scid] = int(mid - ours)

	## Just for testing. REMOVE ME.
	needs_fill['715322x2292x1'] = needs_drain['715322x2292x1']
	del needs_drain['715322x2292x1']

	for scid_f in needs_fill:
		for scid_d in needs_drain:

			if (needs_fill[scid_f] == 0):
				break

			if (needs_drain[scid_d] == 0):
				continue

			plugin.log(f"Proc {scid_d} = {needs_drain[scid_d]} and {scid_f} = {needs_fill[scid_f]}")

			if (needs_fill[scid_f] > needs_drain[scid_d]):
				amount = needs_drain[scid_d]
			else:
				amount = needs_fill[scid_f]

			plugin.log(f"Send {amount} from {scid_d} to {scid_f}")

			needs_drain[scid_d] -= amount
			needs_fill[scid_f] -= amount

	return reply


@plugin.init()
def init(options, configuration, plugin):
    plugin.log("Plugin brian.py initialized")

plugin.run()