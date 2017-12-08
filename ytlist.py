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
	print "# URL: "      +thelist['url']
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
	fp.write("# URL: "  +thelist['url']+"\n") 
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
 
#-------------------------------------------------------------------------------
def load_list(uid,uid_type): 

	load_function = { "ytlist": ytlist_extract, "playlist": playlist_extract, 
			  "channel": playlist_extract, "user" : playlist_extract }  	# channel is same thing as user

	# --------------- 
	page = get_page(uid_type,uid) 
	thelist = { 'list_id': uid, 'list_type' : uid_type, 'url' : page['url'] } 
	
	if( load_function.has_key(uid_type) ): 
		load_function[uid_type](page,thelist) 
	else:
		print "Error: unknown uid_type '{ }' not supported".format(uid_type) 
		return thelist 

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
	v['title']   = clean_up_title(vmeta['title']) if vmeta.has_key('title') else "<no_title>" 
	v['duration'] = vmeta['duration'] if vmeta.has_key('duration') else "--:--" 
	#print "@@>","vid:"+v['vid']+" max_res="+v['max_res']+" Dur:"+v['duration']+"\n"
	flags = "V" if vmeta['type'] == "video" else "A"
	flags = flags + "-$" if (vmeta['paid'] == True) else flags  
	flags = flags + "-x" if (vmeta['isFamilyFriendly'] == True) else flags 

	v['flags'] = flags
	v['vmeta'] = vmeta 

	status_update(v['index'],v['vid'],v['title']) 
	return v 
	

#-------------------------------------------------------------------------------
# Functions that parse standard lists : i.e. Playlist, User, Channel 

def load_more_ajax(url,uid_type):
	logr = logging.getLogger() 

	logr.debug("Getting the page: %s",url) 

	response = urllib.urlopen(url)
	code = response.getcode() 
	if(code != 200):
		logm.critical("Error fetching ajax response") 
		return { 'error' : -1} 

	data = json.load(response) 
	if not data.has_key('content_html') or (data['content_html'] == ""):
		print "Load more button in error. skipping..."
		return { 'error' : 1, 'list_content': None, 'lm_widget': None} 
	
	if(uid_type == "playlist"): 
		data['content_html'] = "<table id='pl-video-table'><tbody>"+data['content_html']+"</tbody></table>"

	list_content = html.fromstring(data['content_html'])
	if(len(data['load_more_widget_html'])>0): 
		lm_widget = html.fromstring(data['load_more_widget_html']) 
	else: 
		lm_widget = None 

	return { 'error' : 0, 'list_content': list_content, 'lm_widget': lm_widget} 

def parse_lmwidget(lmore,uid_type): 

	lmw_xpath = { "playlist": '//button[@data-uix-load-more-target-id="pl-load-more-destination"]/@data-uix-load-more-href', 
		      "channel" : '//button[@data-uix-load-more-target-id="channels-browse-content-grid"]/@data-uix-load-more-href',
		      "user"	: '//button[@data-uix-load-more-target-id="channels-browse-content-grid"]/@data-uix-load-more-href'
		    }

	lmurl = ""
	if(lmore == None): 
		return lmurl 

	lmurlobj = lmore.xpath(lmw_xpath[uid_type])
	if(len(lmurlobj) > 0): 
		lmurl = youtube+lmurlobj[0] 
	return lmurl 

def list_parse(list_content,uid_type,last=0):

	xpath_master = { 
		   'playlist' :
		  { "box"   : '//table[@id="pl-video-table"]/tbody/tr',
		    "vid"   : ".//@data-video-id",
		    "title" : "./@data-title",
		    "time"  : "./td[@class='pl-video-time']/div/div[@class='timestamp']/span/text()" },
		   'channel' : 
		  { "box"   : '//li[@class="channels-content-item yt-shelf-grid-item"]',
		    "vid"   : "./div/@data-context-item-id",
		    "title" : ".//a/@title",
		    "time"  : ".//span[@class='video-time']/span/text()" },
		   'user' : 
		  { "box"   : '//li[@class="channels-content-item yt-shelf-grid-item"]',
		    "vid"   : "./div/@data-context-item-id",
		    "title" : ".//a/@title",
		    "time"  : ".//span[@class='video-time']/span/text()" } 
		}

	
	plist = list() 
	if list_content is None:
		return plist;
	
	xpath = xpath_master[uid_type] 
	i = last
	for l in list_content.xpath(xpath['box']):
		vid   = l.xpath(xpath['vid'])[0]
		title = clean_up_title(l.xpath(xpath['title'])[0]) 
		t     = l.xpath(xpath['time']) 
		time = t[0]  if (t) else "00:00" 
		i = i+1 
		plitem = create_default_vid_meta(vid,title)  
		plitem['index'] = i
		plitem['duration'] = str(time)  
		plist.append(plitem) 

	return plist 
	
#-------------------------------------------------------------------------------
# funcitons specific to type "Playlist" 

def playlist_extract(page,thelist): 

	xpath_master = { "playlist" : {  'title' : '//h1[@class="pl-header-title"]/text()' ,
	   	   			 'owner' : '//h1[@class="branded-page-header-title"]/span/span/span/a/text()' }, 
			  "channel" : {  'title' : '//span[@class="qualified-channel-title-text"]/a/text()',
					 'owner' : '//span[@class="qualified-channel-title-text"]/a/text()'  }, 
			  "user"    : {  'title' : '//span[@class="qualified-channel-title-text"]/a/text()',
					 'owner' : '//span[@class="qualified-channel-title-text"]/a/text()'  }  } 
	
	uid_type = thelist["list_type"]

	title_xpath = xpath_master[uid_type]['title'] 
	owner_xpath = xpath_master[uid_type]['owner'] 
	
	tree = html.fromstring(page['contents']) 

	t = tree.xpath(title_xpath)
	thelist['title'] = clean_up_title(t[0]) if (len(t) > 0) else "no_name list" 
	thelist['owner'] = tree.xpath(owner_xpath)[0]
		
	plist = list_parse(tree,uid_type) 
	lmurl = parse_lmwidget(tree,uid_type)  
	
	count = 1
	while (len(lmurl)>0): 
		#print "Loading next ... "+lmurl 
		ajax_resp = load_more_ajax(lmurl,thelist["list_type"]) 
		if(ajax_resp['error'] <0 ): 
			print "Error extracting load more... returning the list" 
			break
		pl = list_parse(ajax_resp['list_content'],uid_type,len(plist))
		plist.extend(pl)
		lmurl = parse_lmwidget(ajax_resp['lm_widget'],uid_type) 
		count += 1
	
	thelist['list'] = plist

	return

## -------------- function to parse ytlist ------------------------

def ytlist_extract(page,thelist):
	i=0
	url_list = list() 
	pre_comment = "" 

	ytlines = page['contents'].split("\n")
	thelist['title'] = thelist['list_id'].rsplit("/",1)[-1] 
	thelist['owner'] = "ytdragon" 

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
			attrs = details[1].split("\t") if (len(details) > 1) else list() 

			status, uid_type, uid = get_uid_from_ref(uidref) 
			
			#if(uid_type != "video"): 
			#	print "only video type is supported!" 
			#	pre_comment = pre_comment + "#" + line 
			#	continue 
			
			vid = create_default_vid_meta(uid) 
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


