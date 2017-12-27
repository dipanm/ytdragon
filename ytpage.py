#!/usr/bin/python3 -u 

import os 
import logging
import string
import re
import urllib
from urllib import parse as  urlparse
import pprint 
from lxml import html 

default_host = "youtube.com" 
default_hurl = "https://"+default_host 

skip_codes  = { "#": "COMMENT", "@" : "DONE", "?" : "BAD_ITEM", "=" : "COMMAND" } 
uidtype_map = { "v"	: "video", 	"vid"	: "video",	"video"		: "video",
	      	"c"	: "channel",	"ch" 	: "channel", 	"channel"	: "channel",
	      	"u"	: "user", 	"usr"	: "user", 	"user"		: "user",
	      	"p"	: "playlist", 	"pl"	: "playlist", 	"playlist"	: "playlist", 
	      	"l" 	: "ytlist", 	"yl"	: "ytlist", 	"ytlist"	: "ytlist" } 

url_map = { 	"UNKNOWN" : "", 
		"ytlist"  : "file://<ID>",
		"video"   : "/watch?v=<ID>", 
		"playlist": "/playlist?list=<ID>", 
		"user"    : "/user/<ID>/videos"	,
		"channel" : "/channel/<ID>/videos"	} 

def extract_id_q(parsed_url,query): 
	qdict = urlparse.parse_qs(parsed_url.query)
	plid = qdict[query][0] if query in qdict else "UNKNOWN_ID" 
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
                "playlist" : { "uid_type":"playlist","extract_id": extract_id_q, "key_ref": "list"	},
                "user"     : { "uid_type":"user",    "extract_id": extract_id_p, "key_ref": "user" 	},
                "channel"  : { "uid_type":"channel", "extract_id": extract_id_p, "key_ref": "channel" 	}
	   } 

def get_uid_from_ref(uid_str):
	uid_type = "UNKNOWN"
	uid      = "UNKNOWN_ID" 

	if (len(uid_str) == 0 ): 
		return skip_codes["#"], skip_codes["#"], ""

	if(uid_str[0] in skip_codes.keys()) : 
		status = skip_codes[uid_str[0]] 
		uid_str = uid_str[1:] 
	else: 
		status = "OK" 
			
	if re.match('^(http|https)://', uid_str): #and (sp_char == ""):
		parsed_url = urlparse.urlparse(uid_str)
		h = parsed_url.netloc
		path = parsed_url.path
		base_path = path.split("/")[1]

		if default_host not in h: 
			uid_type = "UNKNOWN_HOST" 
		else: 
			if base_path in path_id_map: 
				uid_type = path_id_map[base_path]["uid_type"] 
				uid  = path_id_map[base_path]["extract_id"](parsed_url,path_id_map[base_path]["key_ref"]) 
			else: 
				uid_type = "UNKNOWN_PAGE" 
	else:
		ul = uid_str.split("=",1) 
		uid_type = uidtype_map[ul[0]] if ul[0] in uidtype_map else "UNKNOWN_TYPE"
		if len(ul) > 1 : 
			uid = ul[1].split("/")[0] if (uid_type != "ytlist") else ul[1]
		else: 
			uid = "UNKNOWN_ID" 

	return status, uid_type, uid  

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

	if(pagetype == "ytlist"):
		url = "file://"+os.path.abspath(uid)
	else:
		url = default_hurl+url_map[pagetype].replace("<ID>",uid) 

	response = urllib.request.urlopen(url)
	page['url'] = url
	page['code'] = response.getcode() 
	page['contents'] = response.read().decode('utf-8') 
	page['len']  = len(page['contents']) 

	return page 

