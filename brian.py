#!/usr/bin/env python3

"""
Plugin Descr Here
"""

import pyln.client
import json
import sqlite3

plugin = pyln.client.Plugin()
db = sqlite3.connect("/home/brian/git/plugin-c-lightning/data.db")

@plugin.method("brian")
def brian(plugin):

	""" Function Descr Here """

	reply = {}
	peers = plugin.rpc.listpeers()

	if ('peers' not in peers):
		return reply


	#####################
	## Database Checks
	#####################

	# https://www.sqlite.org/datatype3.html
	# https://www.sqlite.org/cli.html
	# https://bcen.cdmana.com/sqlite/sqlite-python.html

	# Make sure tables exist.

	row = db.execute("select count(*) from sqlite_master where type = 'table' and name = 'channels'").fetchone()
	if (not row[0]):
		db.execute("create table channels(id INTEGER primary key autoincrement, short_channel_id text, msatoshi_total int)")
	row = db.execute("select count(*) from sqlite_master where type = 'table' and name = 'channel_data'").fetchone()
	if (not row[0]):
		db.execute("create table channel_data(id INTEGER primary key autoincrement, channel_id int, time datetime default current_timestamp, connected bool, state text, spendable_msatoshi int, receivable_msatoshi int, fee_base_msat int, fee_proportional_millionths int, in_payments_offered int, in_payments_fulfilled int, in_msatoshi_fulfilled int, out_payments_offered int, out_payments_fulfilled int, out_msatoshi_fulfilled int, fees_collected int)")

	# Populate channels table with any new channels

	for p in peers['peers']:
		if ('channels' not in p):
			continue
		for c in p['channels']:
			if 'short_channel_id' not in c:
				continue

			scid = c['short_channel_id']
			mtot = c['msatoshi_total']
			row = db.execute("SELECT COUNT(*) FROM channels where short_channel_id = ?", [scid]).fetchone()
			if (not row[0]):
				db.execute("insert into channels (short_channel_id, msatoshi_total) values (?,?)", [scid, mtot])
				db.commit()

	# Get interval data

	for p in peers['peers']:
		if ('channels' not in p):
			continue
		for c in p['channels']:
			if 'short_channel_id' not in c:
				continue

			scid = c['short_channel_id']
			row = db.execute("SELECT id FROM channels where short_channel_id = ?", [scid]).fetchone()

			channel_id = row[0]
			conn = p['connected']
			state = c['state']
			spendable_msatoshi = c['spendable_msatoshi']
			receivable_msatoshi = c['receivable_msatoshi']
			fee_base_msat = c['fee_base_msat']
			fee_proportional_millionths = c['fee_proportional_millionths']
			in_payments_offered = c['in_payments_offered']
			in_payments_fulfilled = c['in_payments_fulfilled']
			in_msatoshi_fulfilled = c['in_msatoshi_fulfilled']
			out_payments_offered = c['out_payments_offered']
			out_payments_fulfilled = c['out_payments_fulfilled']
			out_msatoshi_fulfilled = c['out_msatoshi_fulfilled']

			fee_base_msat = fee_base_msat.millisatoshis

			fees_collected = 0
			forwards = plugin.rpc.listforwards(status="settled", out_channel=scid)
			for f in forwards['forwards']:
				fees_collected += f['fee']

			db.execute("insert into channel_data (channel_id, connected, state, spendable_msatoshi, receivable_msatoshi, fee_base_msat, fee_proportional_millionths, in_payments_offered, in_payments_fulfilled, in_msatoshi_fulfilled, out_payments_offered, out_payments_fulfilled, out_msatoshi_fulfilled, fees_collected) values (?,?,?,?,?,?,?,?,?,?,?,?,?, ?)", [channel_id, conn, state, spendable_msatoshi, receivable_msatoshi, fee_base_msat, fee_proportional_millionths, in_payments_offered, in_payments_fulfilled, in_msatoshi_fulfilled, out_payments_offered, out_payments_fulfilled, out_msatoshi_fulfilled, fees_collected])
			db.commit()


	#####################
	## Adjust Fees
	#####################

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
					base = 500
				elif (our_pct >= 85):
					ppm = 1
					base = 500
				elif (our_pct >= 75):
					ppm = 2
					base = 500
				elif (our_pct >= 25):
					ppm = 5
					base = 1000
				elif (our_pct >= 15):
					ppm = 6
					base = 1000
				elif (our_pct >= 5):
					ppm = 7
					base = 1000
				else:
					ppm = 8
					base = 1000

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
