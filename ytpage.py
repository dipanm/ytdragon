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

url_map = { 	"UNKNOWN" : "", 
		"video"   : "/watch?v=<ID>", 
		"list"    : "/playlist?list=<ID>", 
		"user"    : "/user/<ID>/videos"	,
		"channel" : "/channel/<ID>"	} 

def extract_id_q(parsed_url,query): 
	qdict = urlparse.parse_qs(parsed_url.query)
	plid = qdict[query][0] if qdict.has_key(query) else "UNKNOWN_ID" 
	return plid 

def extract_id_p(parsed_url,pkey): 
	path = parsed_url.path.split('/') 
	i = 0 
	for p in path : 
		if pkey in p : 
			break;
		else: 
		   i += 1 
	uid = path[i+1] if (i <= len(path)) else "UNKNOWN_ID" 
	return uid 

path_id_map ={ 	"watch"    : { "uid_type":"video",   "extract_id": extract_id_q, "key_ref": "v" 	},
                "playlist\?" : { "uid_type":"list",    "extract_id": extract_id_q, "key_ref": "list"	},
                "user"     : { "uid_type":"user",    "extract_id": extract_id_p, "key_ref": "user" 	},
                "channel"  : { "uid_type":"channel", "extract_id": extract_id_p, "key_ref": "channel" 	}
	   } 

def get_uid_from_ref(uid_str):
	special_chars = { '#', '=', '@', '?' } 

	sp_char  = ""
	uid_type = "UNKNOWN"
	status   = "ERROR"  
	uid      = "UNKNOWN_ID" 

	if(uid_str[0] in special_chars) : 
		uid_str = uid_str[1:] 
		sp_char = uid_str[0] 
			
	if re.match('^(http|https)://', uid_str): #and (sp_char == ""):
		parsed_url = urlparse.urlparse(uid_str)
		h = parsed_url.netloc
		path = parsed_url.path 

		if default_host not in h: 
			status = "BAD_HOST" 
		
		else: 
			status = "INCORRECT_PAGE" 	# default if you don't find actual one 
			for idstr in path_id_map.keys(): 
				if idstr in path: 
					uid_type = path_id_map[idstr]["uid_type"] 
					uid  = path_id_map[idstr]["extract_id"](parsed_url,path_id_map[idstr]["key_ref"]) 
					status = "OK" 
					break; 
	else:
		uid = uid_str
		uid_type = "Generic" 
		status = "OK" if uid.isalnum() else "BAD_UID" 

	return status, sp_char, uid_type, uid  

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


def get_page(pagetype,uid):

	page = { 'code' : -1, 'contents' : ""} 

	url = default_hurl+url_map[pagetype].replace("<ID>",uid) 

	response = urllib.urlopen(url)
	page['url'] = url
	page['code'] = response.getcode() 
	page['contents'] = response.read()
	page['len']  = len(page['contents']) 

	return page 

