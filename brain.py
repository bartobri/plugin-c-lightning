#!/usr/bin/env python3.6

"""
Plugin Descr Here
"""

import pyln.client
import json
import sqlite3
import random

plugin = pyln.client.Plugin()

def database_check_tables(db):
	row = db.execute("select count(*) from sqlite_master where type = 'table' and name = 'channels'").fetchone()
	if (not row[0]):
		db.execute("create table channels(id INTEGER primary key autoincrement, short_channel_id text, msatoshi_total int, flags int)")
	row = db.execute("select count(*) from sqlite_master where type = 'table' and name = 'channel_data'").fetchone()
	if (not row[0]):
		db.execute("create table channel_data(id INTEGER primary key autoincrement, channel_id int, time datetime default current_timestamp, connected bool, state text, spendable_msatoshi int, receivable_msatoshi int, fee_base_msat int, fee_proportional_millionths int, in_payments_offered int, in_payments_fulfilled int, in_msatoshi_fulfilled int, out_payments_offered int, out_payments_fulfilled int, out_msatoshi_fulfilled int, fees_collected int, fees_assisted int)")

def database_check_channels(db, peers):
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
				db.execute("insert into channels (short_channel_id, msatoshi_total, flags) values (?,?,?)", [scid, mtot, 0])
				db.commit()

def database_trim_data(db):
	db.execute("delete from channel_data where time <= datetime('now', '-7 day')")
	db.commit()

def database_get_data(db, peers):
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

			fees_assisted = 0
			forwards = plugin.rpc.listforwards(status="settled", in_channel=scid)
			for f in forwards['forwards']:
				fees_assisted += f['fee']

			db.execute("insert into channel_data (channel_id, connected, state, spendable_msatoshi, receivable_msatoshi, fee_base_msat, fee_proportional_millionths, in_payments_offered, in_payments_fulfilled, in_msatoshi_fulfilled, out_payments_offered, out_payments_fulfilled, out_msatoshi_fulfilled, fees_collected, fees_assisted) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [channel_id, conn, state, spendable_msatoshi, receivable_msatoshi, fee_base_msat, fee_proportional_millionths, in_payments_offered, in_payments_fulfilled, in_msatoshi_fulfilled, out_payments_offered, out_payments_fulfilled, out_msatoshi_fulfilled, fees_collected, fees_assisted])
			db.commit()

def fees_adjust(db, config, peers):
	reply = {}

	for p in peers['peers']:

		if ('channels' not in p):
			continue

		for c in p['channels']:

			if 'short_channel_id' in c and c['state'] == 'CHANNELD_NORMAL':
				scid = c['short_channel_id']
				ours = c['spendable_msatoshi']
				theirs = c['receivable_msatoshi']
				ppm = c['fee_proportional_millionths']
				base = c['fee_base_msat'].millisatoshis

				our_pct = int((ours / (ours + theirs)) * 100)

				row = db.execute("SELECT flags FROM channels where short_channel_id = ?", [scid]).fetchone()
				flags = row[0]
				is_filling = flags & 0x00000001

				#####################
				# Adjusting ppm Fee
				#####################

				"""

				ppm = 3
				ppm_min = 3
				ppm_multiplier = 1.04
				ppm_reducer = 0.95
				opf_day_goal = 1

				# Percentage Adjustment

				ppm_pct = ppm
				for i in range(100 - our_pct):
					ppm_pct *= ppm_multiplier

				ppm = ppm_pct

				# Payments Fulfilled Daily Goal Adjustment

				ppm_opf = ppm

				row = db.execute("SELECT id FROM channels where short_channel_id = ?", [scid]).fetchone()
				channel_id = row[0]
				row = db.execute("select out_payments_fulfilled from channel_data where channel_id = ? order by id desc limit 1", [channel_id]).fetchone()
				opf_total = row[0]
				row = db.execute("select out_payments_fulfilled from channel_data where channel_id = ? and time < datetime('now', '-1 day') order by id desc limit 1", [channel_id]).fetchone()
				opf_day = opf_total - row[0]

				if (opf_day < opf_day_goal):
					if (opf_total > 0):
						row = db.execute("select JULIANDAY('now') - JULIANDAY(time) as diff from channel_data where channel_id = ? and out_payments_fulfilled < ? order by id desc limit 1", [channel_id, opf_total]).fetchone()
						if (row == None):
							row = db.execute("select JULIANDAY('now') - JULIANDAY(time) as diff from channel_data where channel_id = ? order by id asc limit 1", [channel_id]).fetchone()
					else:
						row = db.execute("select JULIANDAY('now') - JULIANDAY(time) as diff from channel_data where channel_id = ? order by id asc limit 1", [channel_id]).fetchone()
					opf_days_since_last = int(row[0])
					for i in range(opf_days_since_last):
						ppm_opf *= ppm_reducer
				if (opf_day > opf_day_goal):
					opf_day_extra = opf_day - opf_day_goal
					for i in range(opf_day_extra):
						ppm_opf *= ppm_multiplier

				ppm = ppm_opf

				# Get Integer Value

				ppm = int(ppm)

				# Check Minimum

				if (ppm < ppm_min):
					ppm = ppm_min

				# Set To Zero If We Need To Rebalance

				if (our_pct >= 95):
					ppm = 0

				"""

				#####################
				# Adjusting Fees
				#####################

				# Turning off fee adjustments for now.
				# And turning all is_filling flags off.
				ppm = config['fee-per-satoshi']
				base = config['fee-base']
				if (is_filling == 1):
					flags = flags - 0x00000001
					db.execute("UPDATE channels SET flags = ? where short_channel_id = ?", [flags, scid])
					db.commit()

				"""

				if (is_filling == 1 and our_pct >= 50):
					base = 0
					ppm = 0
				elif (is_filling == 0 and our_pct >= 90):
					base = 0
					ppm = 0
					flags = flags | 0x00000001
					db.execute("UPDATE channels SET flags = ? where short_channel_id = ?", [flags, scid])
					db.commit()
				else:
					if (is_filling == 1):
						flags = flags - 0x00000001
						db.execute("UPDATE channels SET flags = ? where short_channel_id = ?", [flags, scid])
						db.commit()
					base = config['fee-base']
					ppm = config['fee-per-satoshi']

				"""

				#####################
				# Set Channel Fee
				#####################

				if (base != c['fee_base_msat'].millisatoshis or ppm != c['fee_proportional_millionths']):

					plugin.rpc.setchannelfee(scid, base, ppm)

					reply[scid] = {}
					reply[scid]['ours'] = ours
					reply[scid]['theirs'] = theirs
					reply[scid]['our_pct'] = our_pct
					reply[scid]['base_old'] = c['fee_base_msat'].millisatoshis
					reply[scid]['base_new'] = base
					reply[scid]['ppm_old'] = c['fee_proportional_millionths']
					reply[scid]['ppm_new'] = ppm
					reply[scid]['is_filling'] = is_filling

	return reply

def channels_balance(config, peers):

	fill = {}
	drain = {}

	# 100 sats per million = 0.01
	# 50 sats per million = 0.005
	# 25 sats per million = 0.0025
	#fee_per_satoshi = config['fee-per-satoshi']
	#rebalance_maxfeepercent = (fee_per_satoshi / 2) * 0.0001

	rebalance_maxfeepercent = 0.025
	rebalance_msatoshi = 50000000

	for p in peers['peers']:

		if ('channels' not in p):
			continue

		for c in p['channels']:

			if 'short_channel_id' in c and c['state'] == 'CHANNELD_NORMAL':
				scid = c['short_channel_id']
				ours = c['spendable_msatoshi']
				theirs = c['receivable_msatoshi']

				our_pct = int((ours / (ours + theirs)) * 100)

				if (our_pct >= 75):
					amt = ours - ((ours + theirs) / 2)
					if (amt >= rebalance_msatoshi):
						drain[scid] = amt
				elif (our_pct <= 25):
					amt = ((ours + theirs) / 2) - ours
					if (amt >= rebalance_msatoshi):
						fill[scid] = ((ours + theirs) / 2) - ours

	fill = dict(sorted(fill.items(), key=lambda x:x[1], reverse=True))
	drain = dict(sorted(drain.items(), key=lambda x:x[1], reverse=True))

	bad_status = {}
	while (len(list(fill)) > 0 and len(list(drain)) > 0):
		fill_scid = random.choice(list(fill))
		drain_scid = random.choice(list(drain))

		if (fill[fill_scid] < rebalance_msatoshi):
			fill.pop(fill_scid)
			continue
		if (drain[drain_scid] < rebalance_msatoshi):
			drain.pop(drain_scid)
			continue
		if ((fill_scid in bad_status) and bad_status[fill_scid] >= 3):
			fill.pop(fill_scid)
			continue
		if ((drain_scid in bad_status) and bad_status[drain_scid] >= 3):
			drain.pop(drain_scid)
			continue

		plugin.log(f"REBALANCING {drain_scid} and {fill_scid}")
		#fill[fill_scid] -= rebalance_msatoshi
		#drain[drain_scid] -= rebalance_msatoshi

		result = plugin.rpc.rebalance(outgoing_scid=drain_scid, incoming_scid=fill_scid, msatoshi=rebalance_msatoshi, maxfeepercent=rebalance_maxfeepercent, exemptfee=1)
		if (result["status"] == "complete"):
			plugin.log(f"REBALANCE SUCCESS")
			fill[fill_scid] -= rebalance_msatoshi
			drain[drain_scid] -= rebalance_msatoshi
		else:
			if (fill_scid in bad_status):
				bad_status[fill_scid] += 1
			else:
				bad_status[fill_scid] = 1
			if (drain_scid in bad_status):
				bad_status[drain_scid] += 1
			else:
				bad_status[drain_scid] = 1

	reply = {}
	reply['fill'] = fill
	reply['drain'] = drain

	# e.g. lightning-cli rebalance -k outgoing_scid=715198x902x0 incoming_scid=715269x1146x1 msatoshi=50000000 maxfeepercent=0.02 exemptfee=1
	return reply

@plugin.method("brain")
def brain(plugin):

	""" Function Descr Here """

	reply = {}
	db = sqlite3.connect("/home/brian/git/plugin-c-lightning/data.db")
	peers = plugin.rpc.listpeers()
	config = plugin.rpc.listconfigs()

	if ('peers' not in peers):
		return reply

	database_check_tables(db)
	database_check_channels(db, peers)
	database_trim_data(db)
	database_get_data(db, peers)
	#reply = fees_adjust(db, config, peers)
	#reply = channels_balance(peers)

	return reply
	

@plugin.method("braintest")
def braintest(plugin):

	""" Function Descr Here """

	reply = {}

	db = sqlite3.connect("/home/brian/git/plugin-c-lightning/data.db")
	peers = plugin.rpc.listpeers()
	config = plugin.rpc.listconfigs()
	
	#reply = channels_balance(config, peers)

	return reply


@plugin.init()
def init(options, configuration, plugin):
    plugin.log("Plugin brain.py initialized")

plugin.run()
