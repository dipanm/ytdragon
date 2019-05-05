#!/usr/bin/python3 -u 

import pprint 
import datetime
import os 
import sys
import socket 
import getopt
import logging
import subprocess
from io import StringIO
import string
import ssl 
import urllib
import certifi

from xml.dom import minidom
from html.parser import HTMLParser
from ytdragon.utils import clean_up_title

### User Config Variable ----------------------------

quite = False 
enable_line_log = True 
line_log_path  = "./ytdragon.log" 
enable_vid_log  = True 
vidlog_path = "./logs"
deep_debug = False

default_host = "youtube.com" 
default_hurl = "https://"+default_host 

def select_captions(vid, caption_map):
	logr = logging.getLogger(vid) 

	if(len(caption_map) > 0):		# select captions of choosen lang only - remove rest 
		select_map = [ cmap for cmap in caption_map if 'en' in cmap['lang'] ] 
		caption_map = select_map 

	if(len(caption_map) == 1):		# if you are left with only 1 - that's the one you need. 
		return caption_map[0]
	elif (len(caption_map) > 1):		# remove all which are auto generated 
		select_map = [ cmap for cmap in caption_map if not 'auto' in cmap['name'] ] 
		if (len(select_map) == 0): 	
			return caption_map[0] 	# if all were 'auto' generated, select first from the primary lang list
		else:
			return select_map[0] 	# so you have one or more caps from your lang and non-auto-gen - so pick first!
	else:
		return {}  			# When none of them are of your choosen language. 


def select_best_stream(vid_item):
	vid = vid_item['vid']
	stream_map = vid_item['stream_map'] 

	logr = logging.getLogger(vid)
	max_res_std = int(stream_map['std'][0]['res'])	if len(stream_map['std']) > 0 else 0
	max_res_adp = int(stream_map['adp_v'][0]['res'])  if len(stream_map['adp_v']) > 0 else 0

	select_map = dict();
	if(max_res_adp > max_res_std):
		select_map["adp"] = [ stream_map['adp_v'][0], stream_map['adp_a'][0]]
		select_map["out_fmt"] = stream_map['adp_v'][0]['fmt']
		quality = max_res_adp
	else:
		select_map["std"] = stream_map['std'][0]
		select_map["out_fmt"] = stream_map['std'][0]['fmt']
		quality = max_res_std

	# create outfile name here, becaues in future, it will come from config/policy
	#  in that case it will generate filenames as per user's way of formatting
	title = clean_up_title(vid_item['title'])
	select_map["outfile"] = str(title)+"_-_"+str(vid)+"."+select_map["out_fmt"]
	select_map["caption"] = select_captions(vid,stream_map['caption'])
	select_map["quality"] = quality

	return select_map

