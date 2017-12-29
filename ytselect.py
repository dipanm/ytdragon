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

from ytutils import clean_up_title 
from ytutils import write_to_file
from ytutils import print_pretty

from ytmeta import smap_to_str
from ytmeta import load_video_meta
from ytmeta import ytd_exception_meta
from ytpage import get_uid_from_ref 
from ytpage import skip_codes  

from ytmeta import create_default_vid_meta
from ytlist import load_list 
from ytlist import print_list_stats

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

	select_map = list(); 
	if(max_res_adp > max_res_std):
		select_map.append(stream_map['adp_v'][0])
		select_map.append(stream_map['adp_a'][0])
	else:
		select_map.append(stream_map['std'][0])

	caption_map = select_captions(vid,stream_map['caption'])
	if(caption_map):
		select_map.append(caption_map)

	return select_map 


