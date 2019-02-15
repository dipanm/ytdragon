#!/usr/bin/python3 -u 

import pprint
import datetime
import os
import sys, traceback
import socket
import getopt
import logging
import subprocess
from io import StringIO
import string
import ssl
import urllib
import certifi
import time
import json

from xml.dom import minidom
from html.parser import HTMLParser

from ytdragon.ytutils import clean_up_title, write_to_file, print_pretty
from ytdragon.ytmeta import smap_to_str, load_video_meta, ytd_exception_meta
from ytdragon.ytselect import select_best_stream

### User Config Variable ----------------------------

quite = False
enable_line_log = True
line_log_path  = "./ytdragon.log"
enable_vid_log  = True
vidlog_path = "./logs"
deep_debug = True

default_host = "youtube.com"
default_hurl = "https://"+default_host
max_retries = 12	# roughly an hour
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
	sys.stdout.write("\r\tDownload progress: %s %d%% of %d MB " % (cstr,percent, totalSize/1000/1000) )
	sys.stdout.flush()

def check_if_downloaded(filepath, vid_meta):

	if not os.path.isfile(filepath): # No file hence continue to download
		return False

	cmd = ['mediainfo', '--Output=JSON', filepath]
	proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
	proc_out, _ = proc.communicate()

	minfo = json.loads(proc_out)
	extra = minfo['media']['track'][0]['extra']
	if (('IsTruncated' in extra) and (extra['IsTruncated'] == 'Yes') ):
		print("\tFile \"{}\" exist but incomplete. Will resume".format(filepath))
		return False # because file exist but not

	smap = vid_meta['select_map'][0]
	for track in minfo['media']['track']:
		if(track['@type'] == 'Video'):
			res = track['Height']
		if(track['@type'] == 'General'):
			duration = float(track['Duration'])

	if(res == smap['res'] and duration > vid_meta['play_length']*0.98):
		print("\tFile \"{}\" exist. Skipping ...".format(filepath))
		return True

	return False	# finally no exact matching file is found. download again!

def download_stream(url,filename):
	global vid
	logr = logging.getLogger(vid)

	logr.debug("\tSaving URL: %s\n\tto %s",url,filename)
	t0 = datetime.datetime.now()
	socket.setdefaulttimeout(120)
	fname, msg = urllib.request.urlretrieve(url,filename,reporthook=dlProgress)
	t1 = datetime.datetime.now()
	sys.stdout.write("\r")
	sys.stdout.flush()
	logr.debug("%sTime taken %s\n---------------------------------",msg,str(t1-t0))

	return

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

	out_fmt = select_map[0]['fmt'] if(len(select_map)>0 and 'fmt' in select_map[0]) else "mp4"
	outfile = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+out_fmt
 
	if(check_if_downloaded(outfile,vidmeta)):
		return

	separated = 1; 	# Assume sepeated content by default. If not, no need to merge
	temp_files = dict();
	for smap in select_map:
		media = smap['media']

		if(media == "caption"):
			continue
		elif(media == "audio-video"):
			filename = outfile
			separated = 0;
		else:
			filename = folder.rstrip('/')+"/"+str(uid)+"."+str(smap['media'])+"."+str(smap['fmt'])
			temp_files[media] = filename 

		logr.info("\t%s",smap_to_str(smap))
		download_stream(smap['url'],filename)

	if(separated == 1):
		combine_streams(temp_files,outfile,1)

	logr.info("\t[Outfile] '%s'",outfile)

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
			if('title' in e.vidmeta):
				logr.info("\tTitle:'%s'",e.vidmeta['title'])
			if('author' in e.vidmeta):
				logr.info("\tAuthor:'%s'",e.vidmeta['author'])
			if (e.errtype == "PAGE_FETCH_ERR"):
				logr.critical("{} :{}".format(e.errmsg,e.msgstr))
			if (e.errtype == "YOUTUBE_ERROR"):
				logr.critical("{}".format(e.errmsg))
				logr.info("-"*45+"\n"+e.msgstr+"\n"+"-"*45)
			if (e.errtype == "BAD_PAGE"):
				logr.critical(e.errmsg)
				print_pretty(logr,"Parsing failed: vid_meta "+"="*20,e.vidmeta)
			if (e.errtype == "NO_STREAMS"):
				logr.critical(e.errmsg)
				print_pretty(logr,"Parsing failed: vid_meta "+"="*20,e.vidmeta)

			if(deep_debug):
				write_to_file(vid+".html",e.page['contents'])
			return 0

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

	return 1

#---------------------------------------------------------------
# Top level functions for Main

def download_with_retry(item,folder,index=0,retries=max_retries):
	logm = logging.getLogger()

	index_str = "%4d"%(index) if index>0 else ""
	result = 0

	for r in range(0,retries):

		retry_str = "-try(%d)"%(r) if r>0 else ""
		try:
			logm.info("Downloading item %s [%s]: %s %s",index_str,item['vid'],str(datetime.datetime.now()),retry_str)
			result = download_video(item,folder)
			break;	# download successful

		except urllib.error.HTTPError as e:
			logm.info("HTTP Error: %d - %s => Not retrying",e.code,e.msg)
			break;

		except (ConnectionError,ssl.SSLError,urllib.error.URLError,socket.timeout) as e:
			retry_str = "Will retry" if(r < retries) else "Too many retries"
			logm.info("\nNetwork Error: %s Try[%s] => %s",repr(e),r,retry_str)
			r += 1
			time.sleep(2**r)

		except (KeyboardInterrupt) as e:
			logm.error("\n%s => Exiting",repr(e))
			sys.exit(1)

		except Exception as e:
			logm.error("Exception: %s",repr(e))
			traceback.print_exc()
			sys.exit(1)

	return result

def download_list(download_list,folder):
	global vid
	logm = logging.getLogger()

	success = 0
	i = 1
	for item in download_list['list']:
		vid = item['vid']
		success += download_with_retry(item,folder,index=i)
		i += 1
	return success

