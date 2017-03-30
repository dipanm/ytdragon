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
from ytmeta    import load_video_meta
from ytmeta    import ytd_exception_meta
from ytpage  import get_page
from ytpage  import get_plid_from_url

### User Config Variable ----------------------------

quite = False 
enable_line_log = True 
line_log_path  = "./ytdragon.log" 
enable_item_log  = True 
itemlog_path = "./logs"
deep_debug = False

max_threads = 40
load_sequential = False 

youtube = "https://www.youtube.com"
unavail_list = { "[Deleted Video]", "[Private Video]" } 

#---------------------------------------------------------------
# Generic functions for all types of list 

def print_list_header(thelist): 
	print "# Playlist: " +thelist['plid']
	print "# Title: "    +thelist['title']
	print "# Owner: "    +thelist['owner']
	print "# Total: "    +str(thelist['total']) 

def print_list_stats(thelist): 
	plist = thelist['list'] 
	del_items = thelist['total']-len(plist)
	print "# Item count: Total="+str(thelist['total'])+" Available ="+str(len(plist))+" Deleted="+str(thelist['unavail'])+" Duplicate="+str(thelist['duplicate'])

def print_list(thelist): 
	plist = thelist['list'] 
	print_list_header(thelist)
	print_list_stats(thelist)
	print "#--------------------------------------------------------"
	for l in plist: 
		print l['vid']+"\t"+l['max_res']+"\t"+l['title'] 

	return 

def save_list(thelist,filename): 
	plist = thelist['list'] 

	if(filename != ""): 
		fp = open(filename,"w") 
	else: 
		fp = sys.stdout

	fp.write("# Playlist: "+thelist['plid']+"\n") 
	fp.write("# Title: "+thelist['title']+"\n") 
	fp.write("# Owner: "+thelist['owner']+"\n") 
	#fp.write("# URL: "+youtube+"/playlist?=list="+playlist['plid']+"\n") # This needs to change to take care of any type of URL! 
	fp.write("# Item count: Total="+str(thelist['total'])+" Available ="+str(len(plist))+" Deleted="+str(thelist['unavail'])+" Duplicate="+str(thelist['duplicate'])+"\n")
	fp.write("#-------------------------------------------------------\n")
	for l in plist: 
		fp.write(l['vid']+"  "+l['duration'].rjust(8)+"\t"+l['max_res'].rjust(10)+"   "+l['flags'].rjust(3)+"  "+l['author'].ljust(35)+"\t"+l['title']+"\n")
	
	fp.close() 
	return 

def prune_list(thelist): 
	thelist['total'] = len(thelist['list']) 
	thelist['unavail'] = 0 
	thelist['duplicate'] = 0 
	
	seen = set() 
	i = 0 
	n = len(thelist['list']) 
	while i < n : 
		if(thelist['list'][i]['title'] in unavail_list): 
			del thelist['list'][i] 
			thelist['unavail'] += 1
			n = n - 1
		elif(thelist['list'][i]['vid'] in seen): 
			del thelist['list'][i] 
			thelist['duplicate'] += 1
			n = n - 1 
		else :
			seen.add(thelist['list'][i]['vid']) 
			i += 1  
			
	return 
 
#-------------------------------------------------------------------------------
def status_update(i, vid="", title="") :
	lslen = 110 
	sys.stdout.write("\r"+" "*lslen)
		
	if(i > 0) : 
		tstr = title[:72] + "..." if (len(title) > 75) else title 
		status_str = "\rProcessing: %3d :[%s]:%s" % (i, vid, tstr)
		sys.stdout.write(status_str) 
	else:
		sys.stdout.write("\r")

	sys.stdout.flush()
	return 

#-------------------------------------------------------------------------------
# Functions to load_meta_info ... 

def load_meta_info(plist) :
	
	total = len(plist) 
	i = 0 
	for v in plist: 
		i += 1 
		v = load_meta(v) 
	
	status_update(-1) 	
	return plist 

def load_meta_info_parallel(plist) : 	# second attempt 
	
	total = len(plist) 
	newlist = list() 
	thread_count = min(max_threads,total) 
	pool = mp.Pool(thread_count) 
	count = 0
	while (count < total): 
		outq = pool.map(load_meta,plist[count:count+thread_count]) 
		newlist.extend(outq) 
		count += thread_count 

	status_update(-1) 	
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
		v['author']  = e.vidmeta['author'] if e.vidmeta.has_key('author') else "" 
		v['filesize'] = 0 
		v['flags'] = "" 
		return v
	except ValueError: 	## need to debug.. jsonload gets many a times. 
		return v 

	v['max_res'] = str(vmeta['max_res']) 
	v['author']  = vmeta['author'] 
	
	flags = "V" if vmeta['type'] == "video" else "A"
	flags = flags + "-$" if (vmeta['paid'] == True) else flags  
	flags = flags + "-x" if (vmeta['isFamilyFriendly'] == True) else flags 

	v['flags'] = flags

	status_update(v['index'],v['vid'],v['title']) 
	return v 
	
#-------------------------------------------------------------------------------
# funcitons specific to type "Playlist" 

def playlist_load_more_ajax(url):
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

def playlist_parse(list_content,last=0):
	plist = list() 
	count = 1
	tstr = '//table[@id="pl-video-table"]/tbody/tr'
	i = last
	for l in list_content.xpath(tstr):
		vid     = list_content.xpath(tstr+"["+str(count)+"]/@data-video-id")[0] 
		title    = clean_up_title(list_content.xpath(tstr+"["+str(count)+"]/@data-title")[0]) 
		t     = list_content.xpath(tstr+"["+str(count)+"]/td[@class='pl-video-time']/div/div[@class='timestamp']/span/text()")
		time = t[0]  if (t) else "00:00" 
		i = i+1 
		plitem = ({'index': i, 'vid':vid,'title':title,'duration':str(time) }) 
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


def playlist_extract(plid,pl_page): 

	tree = html.fromstring(pl_page['contents'])

	t = tree.xpath('//h1[@class="pl-header-title"]/text()')
	title = clean_up_title(t[0]) if (len(t) > 0) else "unknown title" 
	owner = tree.xpath('//h1[@class="branded-page-header-title"]/span/span/span/a/text()')[0]
	playlist = { 'plid': plid, 'title': title, 'owner': owner } 

	plist = playlist_parse(tree) 
	lmurl = parse_lmwidget(tree) 
	
	count = 1
	while (len(lmurl)>0): 
		#print "Loading next ... "+lmurl 
		ajax_resp = playlist_load_more_ajax(lmurl) 
		if(ajax_resp['error'] <0 ): 
			print "Error extracting load more... returning the list" 
			break
		pl = playlist_parse(ajax_resp['list_content'],len(plist))
		plist.extend(pl)
		lmurl = parse_lmwidget(ajax_resp['lm_widget']) 
		count += 1
	
	playlist['list'] = plist
	prune_list(playlist)
	print_list_header(playlist) 

	if(load_sequential) : 
		playlist['list'] = load_meta_info(plist) 
	else : 
		playlist['list'] = load_meta_info_parallel(plist) 

	return playlist 


