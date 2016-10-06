#!/usr/bin/python -u 

import logging
import string
import re
import urllib
import urlparse
from lxml import html 

from ytutils import clean_up_title 

deep_debug = False
default_host = "youtube.com" 
default_hurl = "https://"+default_host 

# following errors to check 
#  - if the first char belongs to special chars 
#  - if not a "youtube.com" page
#  - if host is youtube page but not a watch page 
#  - if id not alphanumeric both direct or url format 
def get_vid_from_url(string):
	# should this business be kept in the list parsing function? 
	none_chars = { '#', '=' }  # Chars used as: '#' as comment, '=' as command
	skip_chars = { '@', '?' }  # Chars used as: '@' as DONE, '?' as ERROR 
	vid = "INVALID" 
	status = "INVALID"
	
	if( (string == "") or (string[0] in none_chars) ) : 
		return "NONE", "" 

	if(string[0] in skip_chars ):
		return "SKIP", string[1:] 

	if re.match('^(http|https)://', string):
		parsed_url = urlparse.urlparse(string)
		h = parsed_url.netloc
		path = parsed_url.path 
		vid = urlparse.parse_qs(parsed_url.query)['v'][0]

		if default_host not in h: 
			status = "BAD_HOST" 
		if not (path == "/watch"):
			status = "INCORRECT_PAGE" 

		if (status == "INVALID") and (vid != "") and (vid != "INVALID") : 
			status = "OK" 
	else:
		vid = string
		status = "OK" if vid.isalnum() else "BAD_VID" 

	return status, vid 

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

def get_list_page(plref):
	logr = logging.getLogger() 

	plid = get_plid_from_url(plref) 

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

def get_watch_page(vid):

	page = { 'code' : -1, 'contents' : ""} 
	url = "https://www.youtube.com/watch?v="+vid

	response = urllib.urlopen(url)
	page['url'] = url
	page['code'] = response.getcode() 
	page['contents'] = response.read()
	page['len']  = len(page['contents']) 

	return page 


