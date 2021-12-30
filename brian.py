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
	needs_balance = {}

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

				if (ours >= high_thresh or ours <= low_thresh):
					needs_balance[scid] = mid - ours
					## Just for testing. REMOVE ME.
					if scid == "715322x2292x1":
						needs_balance[scid] = abs(needs_balance[scid])

	for scid in needs_balance:
		if needs_balance[scid] == 0:
			continue

		for scid2 in needs_balance:
			if needs_balance[scid2] == 0:
				continue

			sender = ""
			receiver = ""
			amount = 0

			if (needs_balance[scid] > 0 and needs_balance[scid2] < 0):
				if (abs(needs_balance[scid]) > abs(needs_balance[scid2])):
					amount = abs(needs_balance[scid2])
					plugin.log(f"A Send {amount} from {scid2} to {scid}")
					needs_balance[scid] -= amount
					needs_balance[scid2] = 0
				else:
					amount = abs(needs_balance[scid])
					plugin.log(f"B Send {amount} from {scid2} to {scid}")
					needs_balance[scid2] += amount
					needs_balance[scid] = 0
			elif (needs_balance[scid] < 0 and needs_balance[scid2] > 0):
				if (abs(needs_balance[scid]) > abs(needs_balance[scid2])):
					amount = abs(needs_balance[scid2])
					plugin.log(f"C Send {amount} from {scid} to {scid2}")
					needs_balance[scid] += amount
					needs_balance[scid2] = 0
				else:
					amount = abs(needs_balance[scid])
					plugin.log(f"D Send {amount} from {scid} to {scid2}")
					needs_balance[scid2] -= amount
					needs_balance[scid] = 0


	return needs_balance


@plugin.init()
def init(options, configuration, plugin):
    plugin.log("Plugin brian.py initialized")

plugin.run()