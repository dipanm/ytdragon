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
from ytpage  import get_uid_from_ref
from ytlist  import load_list  
from ytlist  import save_list
from ytlist  import print_list_stats

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
	usage_str = "Usage: %s [-o|--outfile=\"outfilename\"] <download_reference>"
	plref = ""
	outfile = ""

	if(len(argv) == 0): 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2) 

	try:
		opts, args = getopt.getopt(argv,"o:",["outfile="])
	except getopt.GetoptError as err:
		logm.error("Error in Options: %s",str(err)) 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)
	
	for opt, arg in opts:
		if opt in ("-o", "--outfile"): 
			outfile = arg

	plref = args[0] if (len(args) > 0) else "" 
	if ( plref  == "" ): 
		logm.critical("Missing Download Reference. Either supply item (id/url)  OR file with url_list") 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)

	return plref, outfile

#---------------------------------------------------------------
# Main function

logm = setup_main_logger() 

plref, outfile = parse_arguments(sys.argv[1:]) 

status, uid_type, plid = get_uid_from_ref(plref) 

if(uid_type != "playlist" and uid_type != "ytlist" ): 
	print "Currently this program only supports 'playlist'. {} is not supported".format(uid_type) 
	exit(2) 

plist = load_list(plid,uid_type) 
print_list_stats(plist) 

if(outfile == ""): 
	outfile = clean_up_title(plist['title'])+".yl"
	print "outfile not supplied. Playlist will be saved in: \"{}\" ".format(outfile) 
try: 
	save_list(plist,outfile)
except (IOError, ValueError) as err: 
	print "Can't save playlist %s:".format(outfile) 

