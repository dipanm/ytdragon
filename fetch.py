#!/usr/bin/python -u 

#--------------------------------------------------------------------------------------------
# Wish list 
#	- deal with network failures. 
#	- deal with resume on socket. (resume partial downloads) 
#	- maintain a trace and don't redownload what you have already got. 
#	- you can also check if the file is physically present. 
#	- needs to see that duration available locally matches with what is claimed by YT
#	- maintain csv generator that can keep the trace. 
#	- read list file which can be a CSV - as extracted by channel decoders / playlist decoders etc. 
#	- mark column that will allow users to select/deselect files required to download 
#	- parallel thread downloading 
#	- proper logging on per download basis. (vid.log) independent of stdout for basic purpose. 
#	- bring ffmpeg output to perstream log 
#	- ffmpeg -vcoded copy doesn't work! 
#	- generalize the output file format 
#	- downalod_stream function should provide data of actual status and details of download (put it to trace)
#	- get watch page to retrive the play duration - dont' need to downloard the full thing for it. 
#--------------------------------------------------------------------------------------------

from lxml import html 
import requests 

import json
import urllib 
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
import urllib2

from xml.dom import minidom
from HTMLParser import HTMLParser

global logging_level
global log_dir 
global stream_log_path

logging_level = logging.DEBUG
log_dir = "./logs" 

def get_watch_page(vid):
	logr = logging.getLogger(vid) 

	url = "https://www.youtube.com/watch?v="+vid
	logr.info("Getting the Watch page: %s",url) 

	page = requests.get(url)
	tree = html.fromstring(page.text) 
	t = tree.xpath('//title/text()')
	title = t[0].replace('\n','').rsplit('-',1)[0].strip() 

	parsed_url = urlparse.urlparse(url)
	vid = urlparse.parse_qs(parsed_url.query)['v'][0]

	logr.info("Title: %s",title)
	logr.debug("VID:%s Page size: %d bytes",vid,len(page.text))

	return { 'title': title, 'vid': vid, 'tree': tree }  

def get_stream_map_serial(tree):

	scripts = tree.xpath('//script/text()') 
	for s in scripts:
		if s.find("ytplayer") != -1 :
			player_script = s
			break; 

	p1 = player_script.find("ytplayer.config") 
	p1 = player_script.find("{",p1)
	nesting = 0
	p2 = p1
	for c in player_script[p1:]:
		if c == "{":
			nesting+= 1
		if c == "}":
			nesting-= 1
		p2 += 1
		if nesting == 0:
			break;

	return player_script[p1:p2]

def parse_stream_map(argstr):
	logr = logging.getLogger(vid) 

	arg_list = json.loads(argstr)
	encoded_map = arg_list['args']['url_encoded_fmt_stream_map'].split(",") 
	encoded_map_adp = arg_list['args']['adaptive_fmts'].split(",")
	
	res_index = { 'small': '240', 'medium': '360', 'high': '480', 'hd720': '720', '1440p': '1440', '1080p': '1080'  } 

	logr.info("\nMedia stream options: Std: %d ADP: %d",len(encoded_map),len(encoded_map_adp))
	fmt_stream_map = list()
	for smap in encoded_map:
		fmt_map_list = smap.split("&") 
		fmt_map = dict({'stream':"std"}) 
		for sm in fmt_map_list:
			pair = sm.split("=")
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			fmt_map.update({str(pair[0]):str(pair[1])}) 
			if pair[0] == "quality":
				fmt_map.update({'res':res_index[pair[1]]}) 
			if pair[0] == "type":
				mime = (pair[1].split(";"))[0]
				#multiplexed standard formats have audio and video both
				#even if their mime says only "video". Hence override 
				#media = ((mime.split("/"))[0])
				media = "audio-video"
				fmt = ((mime.split("/"))[1])
				c = pair[1].find("codec")
				codec = ((pair[1].split("codecs="))[1]).strip("\"") if (c>0) else fmt 
				fmt_map.update({'mime':mime,'media':media,'fmt':fmt,'codec':codec}) 
		
		fmt_stream_map.append(fmt_map)

	fmt_stream_map = sorted(fmt_stream_map, key= lambda k: int(k['res']), reverse=True) 

	adp_stream_map_a = list()
	adp_stream_map_v = list()
	for smap in encoded_map_adp:
		adp_map_list = smap.split("&") 
		adp_map = dict({'stream':"adp"}) 
		for sm in adp_map_list:
			pair = sm.split("=")
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			adp_map.update({str(pair[0]):str(pair[1])}) 
			if pair[0] == "quality":
				adp_map.update({'res':res_index[pair[1]]}) 
			if pair[0] == "size": 
				resl, resr = pair[1].split("x")
				adp_map.update({'res':max(int(resl),int(resr))}) 
			if pair[0] == "type":
				mime = ((pair[1].split(";"))[0])
				media, fmt  = mime.split("/")
				c = pair[1].find("codec")
				codec = ((pair[1].split("codecs="))[1]).strip("\"") if (c>0) else fmt 
				adp_map.update({'mime':mime,'media':media,'fmt':fmt,'codec':codec}) 

		if 'res' not in adp_map:
			adp_map.update({'res':'0'}) 
		# Dropping other than 'mp4' formats as they might not mux with mp4 vid 
		if fmt == "mp4": 
			if media == "video":
				adp_stream_map_v.append(adp_map)
			elif media == "audio":
				adp_stream_map_a.append(adp_map)
			else:
				logr.warning("unknown media ....%s",media) 
			
	adp_stream_map_v = sorted(adp_stream_map_v, key= lambda k: int(k['res']), reverse=True) 
	adp_stream_map_a = sorted(adp_stream_map_a, key= lambda k: int(k['bitrate']), reverse=True) 

	caption_map = list() 
	if(arg_list['args'].has_key('caption_tracks')): 
		caption_str = arg_list['args']['caption_tracks'].split(",") 
		for cmap in caption_str:
			cap_map = dict() 
			cap = cmap.split("&")
			for c in cap: 
				c_attrib = c.split("=") 
				if(c_attrib[0] == 'u'): 
					c_attrib[0] = 'url'
				if(c_attrib[0] == 'lc'): 
					c_attrib[0] = 'lang'
				if(c_attrib[0] == 'n'): 
					c_attrib[0] = 'name'
				c_attrib[1] = urllib.unquote(c_attrib[1]).decode('utf8') 
				c_attrib[1] = urllib.unquote(c_attrib[1]).decode('utf8') 
				cap_map.update({str(c_attrib[0]):str(c_attrib[1])})
				cap_map.update({'media':'caption','fmt':'srt'}) 
			caption_map.append(cap_map)

	return { 'std': fmt_stream_map, 'adp_v': adp_stream_map_v, 'adp_a': adp_stream_map_a, 'caption': caption_map }

def print_smap_detailed(map_name,smap):
	logr = logging.getLogger(vid) 

	logr.debug("%s : %d #############################################",map_name,len(smap)) 
	i = 1; 
	for s in smap:
		logr.debug("%d -----------------------------------",i) 
		for key in sorted(s):
			logr.debug("%s:   %s",key,s[key]) 
		i += 1
		
def print_smap_abridged(map_name,smap):
	logr = logging.getLogger(vid) 

	logr.info("%s Total: %d -----------------------------------------------------",map_name,len(smap))
	for s in smap:
		if s['media'] == "audio-video":
			logr.info("%s (%sp) [%s]",s['quality'],str(s['res']),s['type']) 
		if s['media'] == "video":
			logr.info("%s (%sp) [%s]",s['quality_label'],str(s['size']),s['type']) 
		if s['media'] == "audio":
			logr.info("%s kbps, [%s]",int(s['bitrate'])/1024,s['type']) 
		if s['media'] == "caption":
			logr.info("%s %s, [%s]",s['lang'],s['fmt'],s['name']) 

def print_stream_map_detailed(stream_map):
	print_smap_detailed("Standard",stream_map['std'])
	print_smap_detailed("ADP Video",stream_map['adp_v'])
	print_smap_detailed("ADP Audio",stream_map['adp_a'])
	print_smap_detailed("Captions",stream_map['caption'])
		
	
def print_stream_map_abridged(stream_map):
	print_smap_abridged("Standard",stream_map['std'])
	print_smap_abridged("ADP Video",stream_map['adp_v'])
	print_smap_abridged("ADP Audio",stream_map['adp_a'])
	print_smap_abridged("Captions",stream_map['caption'])


def dlProgress(count, blockSize, totalSize):
	logr = logging.getLogger(vid) 

	if(totalSize > 0):
		percent = int(count*blockSize*100/totalSize)
	else: 
		percent = 0 

	count_p = totalSize/blockSize/100+1
	disp_interval = 5
	if(count == 0):
		logr.info("Filesize %d Bytes",totalSize) 
	if(totalSize > 1000*1000): 
		if((count % (count_p*disp_interval) == 0) or (percent == 100)):
			tnow = datetime.datetime.now()
			logr.info("%s : %d%% - %d of %d MB",str(tnow),percent,(count*blockSize)/1000/1000,(totalSize/1000/1000))

def select_captions(caption_map):
	logr = logging.getLogger(vid) 

	logr.info("Selecting caption")

	if(len(caption_map) > 0):		# select captions of choosen lang only - remove rest 
		select_map = [ cmap for cmap in caption_map if 'en' in cmap['lang'] ] 
		caption_map = select_map 

	if(len(caption_map) == 1):		# if you are left with only 1 - that's the one you need. 
		return caption_map[0]
	elif (len(caption_map) > 1):		# remove all which are auto generated 
		select_map = [ cmap for cmap in caption_map if not 'auto' in cmap['name'] ] 
		print_smap_abridged("Selecting captions:caption_map",caption_map)
		print_smap_abridged("Selecting captions:select_map",select_map)
		if (len(select_map) == 0): 	
			return caption_map[0] 	# if all were 'auto' generated, select first from the primary lang list
		else:
			return select_map[0] 	# so you have one or more caps from your lang and non-auto-gen - so pick first!
	else:
		return {}  			# When none of them are of your choosen language. 


def select_best_stream(stream_map):
	max_res_std = int(stream_map['std'][0]['res'])
	max_res_adp = int(stream_map['adp_v'][0]['res'])

	select_map = list(); 
	if(max_res_adp > max_res_std):
		select_map.append(stream_map['adp_v'][0])
		select_map.append(stream_map['adp_a'][0])
	else:
		select_map.append(stream_map['std'][0])

	caption_map = select_captions(stream_map['caption'])
	if(caption_map):
		select_map.append(caption_map)

	#select_map.append(stream_map['std'][0]);
	return select_map 

def combine_streams(temp_files,outfile,remove_temp_files): 
	logr = logging.getLogger(vid)

	cmd = ["ffmpeg","-y","-i",temp_files['video'],"-i",temp_files['audio'],"-acodec","copy","-vcodec","copy",outfile]
	
	proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False) 
	proc_out, _ = proc.communicate() 

	logr.info(proc_out) 
	return_code = proc.wait()

	if(return_code == 0):
		logr.info("\nFFMPEG conversion completed successfully\n")
	else: 
		logr.info("\nFFMPEG conversion completed with error code. Not deleting the downloaded files.\n")
		remove_temp_files = 0
		
	if(remove_temp_files): 
		logr.info("Removing temp files") 
		for key in temp_files:
			logr.info("%s file: %s",key,temp_files[key]) 
			os.remove(temp_files[key]) 
		logr.info("-----------------------------------") 
		

def convert_time_format(ftime):
    return '%02d:%02d:%02d,%03d'%(
        int(ftime/3600),
        int(ftime/60)%60,
        (int(ftime)%3600)%60,
        int((ftime - int(ftime)) * 1000)
        )


def download_caption(page, select_map,folder):
	logr = logging.getLogger(vid) 
	title = page['title'] 
	uid = page['vid'] 
	path = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+"srt"

	for smap in select_map:
		media = smap['media']
		if(media == "caption"):
			capDom = minidom.parse(
			urllib2.urlopen(smap['url'])
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
			break;


def download_streams(page, select_map,folder):
	logr = logging.getLogger(vid) 

	title = page['title'] 
	uid = page['vid'] 
	out_fmt = "mp4"
 
	separated = 1; 	# Assume sepeated content by default. If not, no need to merge 
	temp_files = dict(); 
	for smap in select_map:
		url = smap['url']
		media = smap['media']
		if(media == "caption"):
			continue
		elif(media == "audio-video"):
			filename = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+str(smap['fmt'])
			separated = 0;
		else:
			filename = folder.rstrip('/')+"/"+str(uid)+"."+str(smap['media'])+"."+str(smap['fmt'])
			temp_files[media] = filename 

		logr.info("\nDownloading %s : Destination=%s",smap['media'],filename) 
		logr.debug("URL: %s\n",smap['url']) 
		t0 = datetime.datetime.now() 
		socket.setdefaulttimeout(120)
		fname, msg = urllib.urlretrieve(url,filename,reporthook=dlProgress) 
		t1 = datetime.datetime.now() 
		logr.info("%sTime taken %s\n---------------------------------",msg,str(t1-t0)) 
	
	if(separated == 1):
		outfile = folder.rstrip('/')+"/"+str(title)+"_-_"+str(uid)+"."+out_fmt 
		combine_streams(temp_files,outfile,0)


def setup_logger(vid):
	if not os.path.exists(log_dir):
	    os.makedirs(log_dir)
	stream_log_path = log_dir.rstrip('/')+"/"+vid+".log"
	logr = logging.getLogger(vid) 
	sfH = logging.FileHandler(stream_log_path)
	sfH.setLevel(logging.DEBUG)
	#sfF = logging.Formatter('%(levelname)s:%(message)s') 
	#sfH.setFormatter(sfF) 
	logr.addHandler(sfH) 
	logr.propagate = False 

	logreq = logging.getLogger("requests") 
	logreq.addHandler(sfH)  
	logreq.propagate = False 


def download_item(vid,folder):
	setup_logger(vid) 
	logr = logging.getLogger(vid) 

	logr.info("==================================================================")
	logr.info("Begining to fetch item %s : %s",vid,str(datetime.datetime.now()))

	watch_page = get_watch_page(vid) 
	argstr =  get_stream_map_serial(watch_page['tree'])
	stream_map = parse_stream_map(argstr)

	print_stream_map_detailed(stream_map)
	print_stream_map_abridged(stream_map)

	select_map = select_best_stream(stream_map) 
	print_smap_abridged("Selected",select_map)

	download_streams(watch_page,select_map,folder)
	download_caption(watch_page,select_map,folder)

	return

def get_vid_from_url(string):
	if re.match('^(http|https)://', string):
		url = string
		para = url.split('?')[1].split(",")
		for p in para:
			key, value = p.split("=")
			if(key == 'v'):
				vid = value 
	else:
		vid = string 

	return vid 
 
def read_list(listfile):
	i=0
	url_list = list() 
	lf  = open(listfile, "r")
	for line in lf:
		if line.strip():
			url_list.append(line.rstrip()) 
		i += 1 

	return  url_list  

def parse_arguments(argv): 
	vid = '' 
	item = ''
	ulist = '' 
	folder = ''
	list_mode = 0 

	try:
		opts, args = getopt.getopt(argv,"f:i:l:",["item=","list="])
	except getopt.GetoptError:
		logr.info("Usage: %s -f|--folder='destination' -i|--item='id'/'watch_url' OR -l|--list='url_list'",sys.argv[0])
		sys.exit(2)
	for opt, arg in opts:
		if opt in ("-f", "--folder"):
			folder = arg
		elif opt in ("-i","--item"):
			item = arg 
			list_mode = 0 
		elif opt in ("-l","--list"):
			ulist = arg
			list_mode = 1 

	if ( folder == ''): 
		logr.info("Missing destination folder. Assuming current working directory") 
		folder = "./" 

	if ( item  == '' and ulist == '' ): 
		logr.info("Missing source. Either supply item (id/url)  OR file with url_list") 
		logr.info("item=%s ulist=%s",item,ulist) 
		logr.info("Usage: %s -f|--folder='destination' -i|--item='id'/'watch_url' OR -l|--list='url_list'",sys.argv[0])
		sys.exit(2)

	return folder, item, ulist, list_mode 

#---------------------------------------------------------------
# Main functions 

logging.basicConfig(filename='ytdragon.log',format='%(asctime)s:[%(levelname)s]:%(message)s',level=logging_level)
logr = logging.getLogger('') 
logr.addHandler(logging.StreamHandler()) 

(folder, item, ulist, list_mode)   = parse_arguments(sys.argv[1:]) 

logr.info("Destination folder %s",folder) 

if(list_mode == 1): 
	url_list = read_list(ulist) 
	logr.info("Downloading %d items from list %s",len(url_list),ulist) 
	for url in url_list:
		vid = get_vid_from_url(url)
		download_item(vid,folder)
else:
	logr.info("Downloading one stream %s",item)  
	vid = get_vid_from_url(item)
	download_item(vid,folder)

logr.info("Good bye... Enjoy the video!") 

