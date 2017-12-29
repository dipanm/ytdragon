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

from ytdownload import download_video
from ytdownload import download_list

### User Config Variable ----------------------------

quite = False 
enable_line_log = True 
line_log_path  = "./ytdragon.log" 
enable_vid_log  = True 
vidlog_path = "./logs"
deep_debug = True

default_host = "youtube.com" 
default_hurl = "https://"+default_host 

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
	
#---------------------------------------------------------------
# Support functions for Main 

def parse_arguments(argv): 
	logm = logging.getLogger() 
	usage_str = "Usage: %s -f|--folder='destination' <download_reference> \n"
	usage_str += " Download Reference can be defined as below \n"
	usage_str += "  It can be direct URL such as http://www.youtube.com/watch?v=<vid> \n"
	usage_str += "  or just v=<vid> or vid=<vid> or video=<vid> \n"
	usage_str += " Youtube Playlists and YT Lists can be directly downloaded from here with following download_refs \n"
	usage_str += " YT List downlad ref: l=<ytlist_file.yl> or yl=<ytlist_file.yl> or ytlist=<ytlist_file.yl>\n"
	usage_str += " Playlist download ref: playlist_url  p=<plid> or pl=<plid> or playlist=<plid>\n"
	usage_str += " Remember no spaces before or after '=' \n" 
	usage_str += " Currently channel and playlist are not supported to be fetched directly so use 'extract' for the same"

	folder = ""

	if (len(argv) == 0) : 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2) 

	try:
		opts, args = getopt.getopt(argv,"f:",["folder="])
	except getopt.GetoptError as err:
		logm.error("Error in Options: %s",str(err)) 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)
	
	for opt, arg in opts:
		if opt in ("-f", "--folder"):
			folder = arg

	if ( folder == ""): 
		logm.warning("Missing destination folder. Assuming './' (current working directory) ") 
		folder = "./" 

	logm.debug("Destination folder for streams: %s",folder) 

	if ( len(args) > 0) : 
		uid_ref = args[0] 
	else : 
		logm.critical("Missing source. supply at least one reference to download") 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)

	return folder, uid_ref  

#---------------------------------------------------------------
# Main function

logm = setup_main_logger() 

(folder, uidref) = parse_arguments(sys.argv[1:]) 

status, uid_type, uid = get_uid_from_ref(uidref)

if(status != "OK") : 
	logm.info("Skipping uid %s: Status %s",uid,status) 
	exit(); 

if (uid_type == "video"):
	logm.info("Downloading video: [%s]",uid) 
	vid = uid
	vid_item = create_default_vid_meta(uid)  
	download_video(vid_item,folder) 

elif( (uid_type == "ytlist") or (uid_type == "playlist") or (uid_type == "channel") ):  
	uid_list = load_list(uid,uid_type)
	download_list(uid_list,folder) 
		
else:
	logm.info("Type currently not supported. or Error in id_reference") 
	logm.info("Status {} id_type {} uid {}".format(status, uid_type, uid)) 

logm.info("Good bye... Enjoy the video!") 

