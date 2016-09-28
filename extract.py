#!/usr/bin/python -u 

#--------------------------------------------------------------------------------------------
# Wish list 
#--------------------------------------------------------------------------------------------

from lxml import html 
import requests 

import json
import pprint 
import datetime
import urlparse
import os 
import sys
import socket 
import re
import getopt
import logging
import subprocess
import StringIO
import string
import ssl 
import urllib
import urllib3
import certifi

import multiprocessing as mp 

from xml.dom import minidom
from HTMLParser import HTMLParser

from ytutils import clean_up_title 
from meta    import load_video_meta
from meta    import ytd_exception_meta

### User Config Variable ----------------------------

quite = False 
enable_line_log = True 
line_log_path  = "./ytdragon.log" 
enable_item_log  = True 
itemlog_path = "./logs"
deep_debug = False

max_threads = 40

youtube = "https://www.youtube.com"
unavail_list = { "[Deleted Video]", "[Private Video]" } 

#### -- Logging Related Functions -------------------

def setup_main_logger():
	logm = logging.getLogger() 	# Basic level is DEBUG only to allow other handlers to work 
	logm.setLevel(logging.DEBUG) 

	cfh = logging.StreamHandler()
	if(quite): 
		cfh.setLevel(logging.WARN)
	else: 
		cfh.setLevel(logging.INFO)
	logm.addHandler(cfh) 

	if(enable_line_log): 
		ifh = logging.FileHandler(line_log_path,mode='a')
		ifh.setLevel(logging.INFO)
		iff = logging.Formatter('%(asctime)s:[%(levelname)s]:%(message)s')
		ifh.setFormatter(iff)
		logm.addHandler(ifh)
 
	return logm
	
#### ------------------------------------------------

def get_list_page(plid):
	logr = logging.getLogger() 

	url = "https://www.youtube.com/playlist?list="+plid
	logr.debug("Getting the page: %s",url) 

	response = urllib.urlopen(url)
	code = response.getcode() 
	if(code != 200):
		logr.error("wrong plid %s\n",plid) 
		return { 'error' : -1, 'plid' : plid } 
	page = response.read()

	if(deep_debug): 
		fp = open(plid+".html","w") 
		if(fp): 
			fp.write(page) 
			fp.close() 

	tree = html.fromstring(page) 
	t = tree.xpath('//h1[@class="pl-header-title"]/text()')
	title = clean_up_title(t[0]) 

	owner = tree.xpath('//h1[@class="branded-page-header-title"]/span/span/span/a/text()')[0]
	logr.debug("PLID:[%s] Title:'%s' %d bytes",plid,title,len(page))

	return { 'title': title, 'plid': plid, 'tree': tree, 'owner': owner, 'error': 0 }  

def get_plid_from_url(string):
	if(string[0] == '?'):
		return '?' 
	if re.match('^(http|https)://', string):
		url = string
		para = url.split('?')[1].split(",")
		for p in para:
			key, value = p.split("=")
			if(key == 'list'):
				plid = value 
	else:
		plid = string 

	return plid 

def load_more_ajax(url):
	logr = logging.getLogger() 

	logr.debug("Getting the page: %s",url) 

	response = urllib.urlopen(url)
	code = response.getcode() 
	if(code != 200):
		logm.critical("Error fetching ajax response") 
		return { 'error' : -1} 

	data = json.load(response) 
	data['content_html'] = "<table id='pl-video-table'><tbody>"+data['content_html']+"</tbody></table>"

	list_content = html.fromstring(data['content_html'])
	if(len(data['load_more_widget_html'])>0): 
		lm_widget = html.fromstring(data['load_more_widget_html']) 
	else: 
		lm_widget = None 

	return { 'error' : 0, 'list_content': list_content, 'lm_widget': lm_widget} 

def parse_playlist(list_content):
	plist = list() 
	count = 1
	tstr = '//table[@id="pl-video-table"]/tbody/tr'
	for l in list_content.xpath(tstr):
		vid     = list_content.xpath(tstr+"["+str(count)+"]/@data-video-id")[0] 
		title    = clean_up_title(list_content.xpath(tstr+"["+str(count)+"]/@data-title")[0]) 
		t     = list_content.xpath(tstr+"["+str(count)+"]/td[@class='pl-video-time']/div/div[@class='timestamp']/span/text()")
		time = t[0]  if (t) else "00:00" 
		plitem = ({'vid':vid,'title':title,'duration':time }) 
		plist.append(plitem) 
		count += 1; 

	return plist 
	
def parse_lmwidget(lmore): 
	lmurl = ""
	if(lmore == None): 
		return lmurl 

	lmurlobj = lmore.xpath('//button[@data-uix-load-more-target-id="pl-load-more-destination"]/@data-uix-load-more-href')
	if(len(lmurlobj) > 0): 
		lmurl = youtube+lmurlobj[0] 
	return lmurl 


#---------------------------------------------------------------
# Top level functions for Main 

def print_playlist_header(playlist): 
	print "# Playlist: "+playlist['plid']
	print "# Title: "+playlist['title']
	print "# Owner: "+playlist['owner']

def print_playlist_stats(playlist): 
	plist = playlist['list'] 
	del_items = playlist['total']-len(plist)
	print "# Item count: Total="+str(playlist['total'])+" Available ="+str(len(plist))+" Unavailable="+str(del_items)

def print_playlist(playlist): 
	plist = playlist['list'] 
	print_playlist_header(playlist)
	print_playlist_stats(playlist)
	print "#--------------------------------------------------------"
	for l in plist: 
		#print l['vid']+"\t"+l['max_res']+"\t"+l['title'] 
		print l['vid']+"\t"+l['title'] 

	return 

def save_playlist(playlist,filename): 
	plist = playlist['list'] 

	if(filename != ""): 
		fp = open(filename,"w") 
	else: 
		fp = sys.stdout

	fp.write("# Playlist: "+playlist['plid']+"\n") 
	fp.write("# Title: "+playlist['title']+"\n") 
	fp.write("# Owner: "+playlist['owner']+"\n") 
	fp.write("# URL: "+youtube+"/playlist?=list="+playlist['plid']+"\n") 
	del_items = playlist['total']-len(plist)
	fp.write("# Item count: Total="+str(playlist['total'])+" Available ="+str(len(plist))+" Deleted="+str(del_items)+"\n")
	fp.write("#-------------------------------------------------------\n")
	for l in plist: 
		fp.write(l['vid']+"\t"+l['duration'].rjust(10)+"\t"+l['title']+"\n")
		#fp.write(l['vid']+"\t"+l['duration'].rjust(10)+"\t"+l['max_res'].rjust(10)+"\t"+l['title']+"\n")
	
	fp.close() 
	return 

#-------------------------------------------------------------------------------

def convert_secs_to_time(seconds) :
	m, s = divmod(int(seconds), 60)
	h, m = divmod(m, 60)
	time = "%d:%02d:%02d" % (h, m, s)
	
	return time 

def status_update(i, total, vid, title,lslen) :
	status_str = "\rProcessing: %d of %d :[%s]:%s" % (i, total,vid, title)
	sys.stdout.write("\r"+" "*lslen) 
	sys.stdout.write(status_str) 
	sys.stdout.flush()
	return len(status_str) 

#-------------------------------------------------------------------------------
def load_meta_info(plist) :
	
	total = len(plist) 
	lslen = 1 
	i = 0 
	for v in plist: 
		i += 1 
		lslen = status_update(i, total,v['vid'],v['title'],lslen) 
		v = load_meta(v) 
		
	sys.stdout.write("\r"+" "*lslen+"\n")
	sys.stdout.flush()

	return plist 

def load_meta_info_parallel(plist) : 	# second attempt 
	
	resultq = mp.Queue() 
	total = len(plist) 
	lslen = 1 
	vmth = list() 
	th_count = 0 
	last_join = 0  

	count = 0
	newlist = list() 
	thread_count = min(max_threads,total) 
	pool = mp.Pool(thread_count) 
	while (count < total): 
		sys.stdout.write("\rProcessing:"+str(count+1)+"-"+str(min(total,count+thread_count))) 
		outq = pool.map(load_meta,plist[count:count+thread_count]) 
		newlist.extend(outq) 
		count += thread_count 

	return newlist

def load_meta(v) :
	v['max_res']  = ""	# This is default if any of the exceptions skip filling them.
	v['filesize'] = 0 
	v['title']    = "" if not v.has_key('title') else v['title'] 
	
	if(v['title'] in unavail_list): 
		return v 
	try : 
		vmeta = load_video_meta(v['vid'],True) 
	except ytd_exception_meta as e:  
		v['max_res'] = e.vidmeta['max_res'] if e.vidmeta.has_key('max_res') else "" 
		v['duration'] = convert_secs_to_time(e.vidmeta['length_seconds']) if e.vidmeta.has_key('length_seconds') else "0:0" 
		v['author']  = e.vidmeta['author'] if e.vidmeta.has_key('author') else "" 
		v['filesize'] = 0 
		v['flags'] = "" 
		return v
	except ValueError: 	## need to debug.. jsonload gets many a times. 
		return v 

	v['max_res'] = vmeta['max_res'] 
	v['duration'] = convert_secs_to_time(vmeta['length_seconds']) 
	v['author']  = vmeta['author'] 
	v['filesize'] = vmeta['filesize'] 
	
	flags = "V" if vmeta['type'] == "video" else "A"
	flags = flags + "-CC" if vmeta['has_caption'] else "" 
	flags = flags + "-$" if vmeta['paid'] else "" 
	flags = flags + "-x" if vmeta['isFamilyFriendly'] else "" 

	v['flags'] = flags
	return v 
	
#-------------------------------------------------------------------------------
def extract_playlist(pl_page): 

	tree = pl_page['tree']
	playlist = { 'plid': pl_page['plid'], 'title': pl_page['title'], 'owner': pl_page['owner'] } 
	plist = parse_playlist(tree) 
	lmurl = parse_lmwidget(tree) 
	
	count = 1
	while (len(lmurl)>0): 
		#print "Loading next ... "+lmurl 
		ajax_resp = load_more_ajax(lmurl) 
		if(ajax_resp['error'] <0 ): 
			print "Error extracting load more... returning the list" 
			break
		pl = parse_playlist(ajax_resp['list_content'])
		plist.extend(pl)
		lmurl = parse_lmwidget(ajax_resp['lm_widget']) 
		count += 1
	
	print_playlist_header(playlist) 

	#plist = load_meta_info(plist) 
	plist = load_meta_info_parallel(plist) 

	playlist['list'] = plist
	playlist['total'] = len(plist) 
	return playlist 

def prune_playlist(playlist): 
	plist = playlist['list'] 
	plist2 = list() 

	for p in plist : 
		if(p['title'] not in unavail_list): 
			plist2.append(p) 
			
	playlist['list'] = plist2 
	return playlist 
 
#---------------------------------------------------------------
# Support functions for Main 

def parse_arguments(argv): 
	logm = logging.getLogger() 
	usage_str = "Usage: %s -p|--playlist=\"playlist_id/playlist_url\" -o|--outfile=\"outfilename\""
	plid = ""
	outfile = ""

	try:
		opts, args = getopt.getopt(argv,"p:o:",["playlist=","outfile="])
	except getopt.GetoptError as err:
		logm.error("Error in Options: %s",str(err)) 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)
	
	if(len(opts) == 0): 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2) 

	for opt, arg in opts:
		if opt in ("-p", "--playlist"):
			plid = get_plid_from_url(arg)
		if opt in ("-o", "--outfile"): 
			outfile = arg

	if ( plid  == "" ): 
		logm.critical("Missing playlist. Either supply item (id/url)  OR file with url_list") 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)

	return plid, outfile

#---------------------------------------------------------------
# Main function

logm = setup_main_logger() 

plid, outfile = parse_arguments(sys.argv[1:]) 

pl_page = get_list_page(plid) 

plist = extract_playlist(pl_page) 

plist = prune_playlist(plist)

save_playlist(plist,outfile) 
print_playlist_stats(plist) 

#logm.info("Good bye... Get those videos!") 

