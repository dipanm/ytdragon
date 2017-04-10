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
from ytmeta  import load_video_meta
from ytmeta  import ytd_exception_meta
from ytmeta  import create_default_vid_meta
from ytpage  import get_page
from ytpage  import get_uid_from_ref
from ytpage  import get_vid_from_url

### User Config Variable ----------------------------

quite = False 
enable_line_log = True 
line_log_path  = "./ytdragon.log" 
enable_item_log  = True 
itemlog_path = "./logs"
deep_debug = False

max_threads = 10
load_sequential = True

youtube = "https://www.youtube.com"
unavail_list = { "[deleted video]", "[private video]" } 

#---------------------------------------------------------------
# Generic functions for all types of list 

def print_list_header(thelist): 
	print "# "+thelist['list_type']+": "+thelist['list_id']	
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

	if(filename == ""): 
		raise ValueError("filename can't be empty") 

	fp = open(filename,"w") 

	fp.write("# "+thelist['list_type']+": "+thelist['list_id']+"\n") 
	fp.write("# Title: "+thelist['title']+"\n") 
	fp.write("# Owner: "+thelist['owner']+"\n") 
	#fp.write("# URL: "+youtube+"/playlist?=list="+playlist['plid']+"\n") # This needs to change to take care of any type of URL! 
	fp.write("# Item count: Total="+str(thelist['total'])+" Available ="+str(len(plist))+" Deleted="+str(thelist['unavail'])+" Duplicate="+str(thelist['duplicate'])+"\n")
	fp.write("#-------------------------------------------------------\n")
	for l in plist: 
		fp.write("v="+l['vid']+"\t"+l['duration'].rjust(8)+"\t"+l['max_res'].rjust(10)+"\t"+l['flags'].rjust(3)+"\t"+l['author'].ljust(35)+"\t"+l['title']+"\n")
	
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
		t = thelist['list'][i]['title'].lower() 
		if(t in unavail_list): 
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
 
def load_list(uid,uid_type): 

	thelist = { 'list_id': uid, 'list_type' : uid_type } 

	# load page -- depending on type. only ytlist is different! TODO 
	if ( uid_type == "ytlist" ): 
		lf  = open(uid, "r")
		ytlines = lf.readlines() 
		thelist['title'] = uid.rsplit("/",1)[-1] 
		thelist['owner'] = "ytdragon" 
		ytlist_extract(ytlines,thelist)
	elif (uid_type == "channel"): 
		ch_page = get_page(uid_type,uid) 
		channel_extract(ch_page['contents'],thelist)
	else: 
		pl_page = get_page(uid_type,uid) 
		playlist_extract(pl_page['contents'],thelist)
	
	prune_list(thelist)
	print_list_header(thelist) 

	if(load_sequential) : 
		thelist['list'] = load_meta_info(thelist['list']) 
	else : 
		thelist['list'] = load_meta_info_parallel(thelist['list']) 

	print_list_stats(thelist)
	return thelist 
 
#-------------------------------------------------------------------------------
def status_update(i, vid="", title="") :
	lslen = 110 
	sys.stdout.write("\r"+" "*lslen)
		
	if(i >= 0) : 
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
	if(v['title'].lower() in unavail_list): # Assuming the default keys are filled.
		return v 
	try : 
		vmeta = load_video_meta(v['vid']) 
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
	
	dur = v['duration'] if v.has_key('duration') else "--:--" 
	#print "vid:"+v['vid']+" max_res="+v['max_res']+" Dur:"+dur+"\n"
	flags = "V" if vmeta['type'] == "video" else "A"
	flags = flags + "-$" if (vmeta['paid'] == True) else flags  
	flags = flags + "-x" if (vmeta['isFamilyFriendly'] == True) else flags 

	v['flags'] = flags
	v['vmeta'] = vmeta 

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
		plitem = create_default_vid_meta(vid,title)  
		plitem['index'] = i
		plitem['duration'] = str(time)  
		plist.append(plitem) 
		count += 1; 

	return plist 
	
def playlist_parse_lmwidget(lmore): 
	lmurl = ""
	if(lmore == None): 
		return lmurl 

	lmurlobj = lmore.xpath('//button[@data-uix-load-more-target-id="pl-load-more-destination"]/@data-uix-load-more-href')
	if(len(lmurlobj) > 0): 
		lmurl = youtube+lmurlobj[0] 
	return lmurl 


def playlist_extract(pl_page,thelist): 

	title_xpath = '//h1[@class="pl-header-title"]/text()'
	owner_xpath = '//h1[@class="branded-page-header-title"]/span/span/span/a/text()'

	tree = html.fromstring(pl_page)

	t = tree.xpath(title_xpath)
	thelist['title'] = clean_up_title(t[0]) if (len(t) > 0) else "no_name list" 
	thelist['owner'] = tree.xpath(owner_xpath)[0]
		
	plist = playlist_parse(tree) 
	lmurl = playlist_parse_lmwidget(tree) 
	
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
	
	thelist['list'] = plist

	return

#-------------------------------------------------------------------------------
# funcitons specific to type "Channel and User"

def channel_load_more_ajax(url):
	logr = logging.getLogger() 

	logr.debug("Getting the page: %s",url) 

	response = urllib.urlopen(url)
	code = response.getcode() 
	if(code != 200):
		logm.critical("Error fetching ajax response") 
		return { 'error' : -1} 

	data = json.load(response) 

	list_content = html.fromstring(data['content_html'])	# 'Content_html' is part of Ajax response. But we must check 
	if(len(data['load_more_widget_html'])>0): 
		lm_widget = html.fromstring(data['load_more_widget_html']) 
	else: 
		lm_widget = None 

	return { 'error' : 0, 'list_content': list_content, 'lm_widget': lm_widget} 


def channel_parse(list_content,last=0):
	plist = list() 
	count = 1
	tstr = '//li[@class="channels-content-item yt-shelf-grid-item"]'
	i = last
	for l in list_content.xpath(tstr):
		vid   = list_content.xpath(tstr+"["+str(count)+"]/div/@data-context-item-id")[0] 
		title = clean_up_title(list_content.xpath(tstr+"["+str(count)+"]//a/@title")[0])
		t = 	list_content.xpath(tstr+"["+str(count)+"]//span[@class='video-time']/span/text()")
		time = t[0]  if (t) else "00:00" 
		i = i+1 
		plitem = create_default_vid_meta(vid,title)  
		plitem['index'] = i
		plitem['duration'] = str(time)  
		plist.append(plitem) 
		count += 1; 

	return plist 

def channel_parse_lmwidget(lmore): 
	lmurl = ""
	if(lmore == None): 
		return lmurl 

	lmurlobj = lmore.xpath('//button[@data-uix-load-more-target-id="channels-browse-content-grid"]/@data-uix-load-more-href')
	if(len(lmurlobj) > 0): 
		lmurl = youtube+lmurlobj[0] 
	return lmurl 


def channel_extract(ch_page,thelist): 

	title_xpath = '//span[@class="qualified-channel-title-text"]/a/text()'
	#owner_xpath = '//h1[@class="branded-page-header-title"]/span/span/span/a/text()'

	tree = html.fromstring(ch_page)

	t = tree.xpath(title_xpath)
	thelist['title'] = clean_up_title(t[0]) if (len(t) > 0) else "unknown channel" 
	thelist['owner'] = thelist['title'] 	# channel / user has no seperation from title and owner 
		
	plist = channel_parse(tree)
	lmurl = channel_parse_lmwidget(tree) 
	
	count = 1
	while (len(lmurl)>0): 
		#print "Loading next ... "+lmurl 
		ajax_resp = channel_load_more_ajax(lmurl) 
		if(ajax_resp['error'] <0 ): 
			print "Error extracting load more... returning the list" 
			break
		pl = channel_parse(ajax_resp['list_content'],len(plist))
		plist.extend(pl)
		lmurl = channel_parse_lmwidget(ajax_resp['lm_widget']) 
		count += 1

	thelist['list'] = plist

	return


## -------------- function to parse ytlist ------------------------

def ytlist_extract(ytlines,thelist):
	i=0
	url_list = list() 
	pre_comment = "" 
	v = 0
	for line in ytlines:
		if line.strip():
			vid = dict() 
			l = line.rstrip().split("#",1) 

			comment = l[1] if (len(l) > 1) else "" 
		
			if( l[0] == ""): 	# so no details only comment 
				pre_comment = pre_comment + comment + "\n"
				continue 
			else: 
				details = l[0].split('\t',1) 

			uidref = details[0] 
			attrs = details[1].split("\t") if (len(details) > 0) else list() 

			status, uid  = get_vid_from_url(uidref) 
			#status, uid_type, uid = get_uid_from_ref(uidref) 
			
			#if(uid_type != "video"): 
			#	print "only video type is supported!" 
			#	pre_comment = pre_comment + "#" + line 
			#	continue 
			
			vid['status']   = status
			#vid['uid_type'] = uid_type
			vid['vid']      = uid 
			vid['attrs']    = attrs 
			vid['pre_comment'] = pre_comment 
			pre_comment = "" 
			vid['comment']  = comment 
			vid['title'] = "" 
			vid['index'] = v 
			url_list.append(vid) 
			v = v+1 
				
			#attrs = l[0].split('\t') 
			#attrs = [attr.strip() for attr in attrs if attr.strip()] 
			#id_str = attrs[0] if(len(attrs) > 0) else "" 
			#vid["comment"] = l[1].strip() if(len(l) > 1) else "" 
			#vid["status"], vid["uid_type"], vid["vid"] = get_uid_from_ref(id_str) 
			#vid["attrs"] = attrs[1:] if (len(attrs)>0) else "" 
			#vid["title"] = "" 	# we don't know yet. 
			#url_list.append(vid) 
			#v = v+1 if(vid['uid_type'] == "video") else v 
				
		i += 1 

	#pprint.pprint(url_list) 
	thelist['list'] = url_list 
	return 


