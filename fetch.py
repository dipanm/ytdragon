#!/usr/bin/python -u 

import pprint 
import datetime
import os 
import sys
import socket 
import getopt
import logging
import subprocess
import StringIO
import string
import ssl 
import urllib
import certifi

from xml.dom import minidom
from HTMLParser import HTMLParser

from ytutils import clean_up_title 
from ytutils import write_to_file
from ytutils import print_pretty

from ytmeta import smap_to_str
from ytmeta import load_video_meta
from ytmeta import ytd_exception_meta
from ytpage import get_vid_from_url 
from ytpage import get_uid_from_ref 
from ytpage import skip_codes  

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
	
def setup_vid_logger(vid):
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
	logm = logging.getLogger() 
	logr = logging.getLogger(vid) 

	counter_str = [ "|","/","-","\\"]
	cstr = counter_str[(count/100)%4] 

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
		

def select_captions(caption_map):
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


def select_best_stream(stream_map):
	logr = logging.getLogger(vid)
	max_res_std = int(stream_map['std'][0]['res'])	if len(stream_map['std']) > 0 else 0 
	max_res_adp = int(stream_map['adp_v'][0]['res'])  if len(stream_map['adp_v']) > 0 else 0 

	select_map = list(); 
	if(max_res_adp > max_res_std):
		select_map.append(stream_map['adp_v'][0])
		select_map.append(stream_map['adp_a'][0])
	else:
		select_map.append(stream_map['std'][0])

	caption_map = select_captions(stream_map['caption'])
	if(caption_map):
		select_map.append(caption_map)

	return select_map 

def combine_streams(temp_files,outfile,remove_temp_files): 
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
		

def convert_time_format(ftime):
    return '%02d:%02d:%02d,%03d'%(
        int(ftime/3600),
        int(ftime/60)%60,
        (int(ftime)%3600)%60,
        int((ftime - int(ftime)) * 1000)
        )


def download_caption(vidmeta, folder):
	logr = logging.getLogger(vid) 

	title = clean_up_title(vidmeta['title']) 
	uid = vidmeta['vid'] 
	select_map = vidmeta['select_map']
	path = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+"srt"

	for smap in select_map:
		media = smap['media']
		if(media == "caption"):
			capDom = minidom.parse(
			urllib.urlopen(smap['url'])
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
		fname, msg = urllib.urlretrieve(url,filename,reporthook=dlProgress) 
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
	logr = setup_vid_logger(vid) 

	if vid_item.has_key('vmeta'):   
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
	 
	vidmeta['select_map'] = sl =  select_best_stream(smap) 
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

elif( (uid_type == "ytlist") or (uid_type == "playlist")):  
	uid_list = load_list(uid,uid_type)
	download_list(uid_list,folder) 
		
else:
	logm.info("Type currently not supported. or Error in id_reference") 
	logm.info("Status {} id_type {} uid {}".format(status, uid_type, uid)) 

logm.info("Good bye... Enjoy the video!") 

