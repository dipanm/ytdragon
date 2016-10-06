#!/usr/bin/python -u 

import logging
import string
import re
import urllib
from lxml import html 

from ytutils import clean_up_title 

deep_debug = False

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


