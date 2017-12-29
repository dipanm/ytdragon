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

from ytselect import select_best_stream
from ytselect import select_captions

### User Config Variable ----------------------------

quite = False 
enable_line_log = True 
line_log_path  = "./ytdragon.log" 
enable_vid_log  = True 
vidlog_path = "./logs"
deep_debug = True

default_host = "youtube.com" 
default_hurl = "https://"+default_host 

vid = ""

def convert_time_format(ftime):
    return '%02d:%02d:%02d,%03d'%(
        int(ftime/3600),
        int(ftime/60)%60,
        (int(ftime)%3600)%60,
        int((ftime - int(ftime)) * 1000)
        )

def setup_vid_logger(v_id):
	global vid 
	vid = v_id 
	logr = logging.getLogger(vid) 

	if(enable_vid_log):
		if not os.path.exists(vidlog_path):
			os.makedirs(vidlog_path)	
		logr.addHandler(logging.FileHandler(vidlog_path.rstrip('/')+"/"+vid+".log")) 
		logr.setLevel(logging.DEBUG)
	else: 
		logr.addHandler(logging.NullHandler())

	logr.propagate = True 	# Error and Info will reflect to the root logger as well 
	return logr 

#==== Download Related funcitons ===============================================
def dlProgress(count, blockSize, totalSize):
	global vid 
	logm = logging.getLogger() 
	logr = logging.getLogger(vid) 

	counter_str = [ "|","/","-","\\"]
	cstr = counter_str[(int(count/100))%4] 

	if(totalSize > 0):
		percent = int(count*blockSize*100/totalSize)
	else: 
		percent = 0 

	count_p = totalSize/blockSize/100+1
	disp_interval = 5
	if(count == 0):
		logr.debug("Filesize %d Bytes",totalSize) 
	if(totalSize > 1000*1000): 
		if((count % (count_p*disp_interval) == 0) or (percent == 100)):
			tnow = datetime.datetime.now()
			logr.debug("%s : %d%% - %d of %d MB",str(tnow),percent,(count*blockSize)/1000/1000,(totalSize/1000/1000))
			#logm.info("%d",percent) 
	sys.stdout.write("\r\tDownload progress: %s %d%% of %d MB " % (cstr,percent, totalSize/1000/1000) )
	sys.stdout.flush()
		

def combine_streams(temp_files,outfile,remove_temp_files): 
	global vid 
	logr = logging.getLogger(vid)

	cmd = ["ffmpeg","-y","-i",temp_files['video'],"-i",temp_files['audio'],"-acodec","copy","-vcodec","copy",outfile]
	
	proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False) 
	proc_out, _ = proc.communicate() 

	logr.debug(proc_out) 
	return_code = proc.wait()

	if(return_code == 0):
		logr.debug("\n\tFFMPEG Muxing successful.")
	else: 
		logr.error("\n\tFFMPEG conversion completed with error code. Not deleting the downloaded files.")
		remove_temp_files = 0
		
	if(remove_temp_files): 
		logr.debug("Removing temp files") 
		for key in temp_files:
			logr.debug("%s file: %s",key,temp_files[key]) 
			os.remove(temp_files[key]) 
		

def download_caption(vidmeta, folder):
	global vid 
	logr = logging.getLogger(vid) 

	title = clean_up_title(vidmeta['title']) 
	uid = vidmeta['vid'] 
	select_map = vidmeta['select_map']
	path = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+"srt"

	for smap in select_map:
		media = smap['media']
		if(media == "caption"):
			capDom = minidom.parse(
			urllib.request.urlopen(smap['url'])
			)
			texts = capDom.getElementsByTagName('text')
			hp = HTMLParser()
			f = open(path,'w')
			for i, text in enumerate(texts):
				fstart = float(text.getAttribute('start'))
				start = convert_time_format(fstart)
				fdur = float(text.getAttribute('dur'))
				dur = convert_time_format(fstart+fdur)
				t = text.childNodes[0].data
				f.write('%d\n'%(i))
				f.write('%s --> %s\n'%(start, dur))
				f.write(hp.unescape(t).encode(sys.getfilesystemencoding()))
				f.write('\n\n')
			logr.info("\t%s\n\tSaved in: => %s",smap_to_str(smap),path) 
			break;


def download_streams(vidmeta, folder):
	global vid 
	vid = vidmeta['vid']
	logr = logging.getLogger(vid) 

	title = clean_up_title(vidmeta['title']) 
	uid = vidmeta['vid'] 
	select_map = vidmeta['select_map']
	out_fmt = "mp4"
 
	separated = 1; 	# Assume sepeated content by default. If not, no need to merge 
	temp_files = dict(); 
	for smap in select_map:
		url = smap['url']
		media = smap['media']
		if(media == "caption"):
			continue
		elif(media == "audio-video"):
			outfile = filename = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+str(smap['fmt'])
			separated = 0;
		else:
			filename = folder.rstrip('/')+"/"+str(uid)+"."+str(smap['media'])+"."+str(smap['fmt'])
			temp_files[media] = filename 

		logr.info("\t%s",smap_to_str(smap)) 
		logr.debug("\tSaving URL: %s\n\tto %s",smap['url'],filename) 
		t0 = datetime.datetime.now() 
		socket.setdefaulttimeout(120)
		fname, msg = urllib.request.urlretrieve(url,filename,reporthook=dlProgress) 
		t1 = datetime.datetime.now() 
		sys.stdout.write("\r")
		sys.stdout.flush()
		logr.debug("%sTime taken %s\n---------------------------------",msg,str(t1-t0)) 
	
	if(separated == 1):
		outfile = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+out_fmt 
		combine_streams(temp_files,outfile,1)

	logr.info("\t[Outfile] '%s'",outfile)

#---------------------------------------------------------------
# Top level functions for Main 

def download_video(vid_item,folder):
	global vid 
	vid = vid_item['vid'] 
	logr = setup_vid_logger(vid) 

	if 'vmeta' in vid_item:   
		vidmeta = vid_item['vmeta'] 
	else: 
		try:
			vidmeta = load_video_meta(vid_item['vid'])
		except ytd_exception_meta as e: 
			if (e.errtype == "PAGE_FETCH_ERR"): 
				logr.critical("\t{} :{}".format(e.errmsg,e.msgstr))
			if (e.errtype == "YOUTUBE_ERROR"): 
				logr.critical(e.errmsg) 
				logr.info("-"*45+"\n"+e.msgstr+"\n"+"-"*45) 
			if (e.errtype == "BAD_PAGE") : 
				logr.critical("\t"+e.errmsg) 
				print_pretty(logr,"Parsing failed: vid_meta "+"="*20,e.vidmeta) 
			if (e.errtype == "NO_STREAMS") : 
				logr.info("\tTitle:'%s'\n\tAuthor:'%s'",e.vidmeta['title'],e.vidmeta['author'])  
				logr.critical("\t"+e.errmsg) 
				print_pretty(logr,"Parsing failed: vid_meta "+"="*20,e.vidmeta) 
					
			if(deep_debug): 
				write_to_file(vid+".html",e.page['contents']) 
			return 

	print_pretty(logr,"Parsing successful: vid_meta "+"="*20,vidmeta) 
	smap = vidmeta['stream_map']
	sm = smap['std'] + smap['adp_v'] + smap['adp_a'] + smap['caption'] 
	logr.debug("= Available Streams: "+"="*25+"\n"+"\n".join(map(smap_to_str,sm)))
	 
	vidmeta['select_map'] = sl =  select_best_stream(vidmeta) 
	logr.debug("= Selected Streams: "+"="*25+"\n"+"\n".join(map(smap_to_str,sl))+"\n")  

	# stream_map, select_map can be public elements so that they can be logged and print outside. 
	logr.info("\tTitle:'%s'\n\tAuthor:'%s'",vidmeta['title'],vidmeta['author'])  
	download_streams(vidmeta,folder)	
	download_caption(vidmeta,folder)
	logr.info("\tFetch Complete @ %s ----------------",str(datetime.datetime.now()))

	return

def download_list(download_list,folder) :
	global vid 
	logm = logging.getLogger() 

	i = 1
	for item in download_list['list']:
		logm.info("Download item %4d [%s]: %s",i,item['vid'],str(datetime.datetime.now()))
		vid = item['vid']
		download_video(item,folder) 
		i += 1
	return


