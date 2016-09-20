#!/usr/bin/python -u 

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

from xml.dom import minidom
from HTMLParser import HTMLParser

from ytutils import clean_up_title 
from ytutils import write_to_file
from ytutils import print_pretty

### User Config Variable ----------------------------

quite = False 
enable_line_log = True 
line_log_path  = "./ytdragon.log" 
enable_item_log  = True 
itemlog_path = "./logs"
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
	
def setup_item_logger(vid):
	logr = logging.getLogger(vid) 

	if(enable_item_log):
		if not os.path.exists(itemlog_path):
			os.makedirs(itemlog_path)	
		logr.addHandler(logging.FileHandler(itemlog_path.rstrip('/')+"/"+vid+".log")) 
		logr.setLevel(logging.DEBUG)
	else: 
		logr.addHandler(logging.NullHandler())

	logr.propagate = True 	# Error and Info will reflect to the root logger as well 
	return logr 


#### ---All functions related loading meta ==========================================

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

def get_watch_page(vid):

	page = { 'code' : -1, 'contents' : ""} 
	url = "https://www.youtube.com/watch?v="+vid

	response = urllib.urlopen(url)
	page['url'] = url
	page['code'] = response.getcode() 
	page['contents'] = response.read()
	page['len']  = len(page['contents']) 

	if(deep_debug): 
		write_to_file(vid+".html",page['contents']) 

	return page 

def extract_player_args(script): 
	player_script = ""

	for s in script:
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
	
def parse_watch_page(page):
	logr = logging.getLogger(vid)

	arg_keys = { 'length_seconds', 'loudness', 'timestamp', 'host_language', 'avg_rating', 'view_count', 'thumbnail_url', 
	   'fmt_list', 'adaptive_fmts', 'url_encoded_fmt_stream_map', 'caption_tracks', 'caption_translation_languages' } 

	prop_keys = { 'og:title' : 'title' , 'og:description' : 'description', 'og:type' : 'type',
			'og:url': 'url', 'og:image': 'fullimage_url', 'og:video:url' : 'embed_url' } 
	iprop_keys = { 'videoId' : 'vid' , 'channelId' : 'chid','datePublished': 'datePublished','genre': 'genre',
			'regionsAllowed': 'regionsAllowed' ,'isFamilyFriendly': 'isFamilyFriendly','paid': 'paid' }

	vid_meta = dict() 
	# extract dom tree of HTML Page
	tree = html.fromstring(page) 

	# extract player script 
	script = tree.xpath('//script[contains(.,"ytplayer")]/text()') 
	player_script = extract_player_args(script) 
	if (player_script == ""):
		error = " ".join(map(str.strip, tree.xpath('//div[@id="player-unavailable"]//text()'))) 
		logr.critical("Video Unavailable: %s",error) 
		return None

	# extract player args from the player script 	
	arg_list = json.loads(player_script)
	if not (arg_list.has_key('args')): 
		logr.critical("The watch page is not a standard youtube page") 
		args = None 
	else:
		args = arg_list['args'] 	

	# populate the attributes
	vid_meta['author'] 		= " ".join(map(str.strip, tree.xpath("//div[@class='yt-user-info']//text()"))).strip()
	vid_meta['author_url'] 		= default_hurl+tree.xpath("//div[@class='yt-user-info']/a/@href")[0]
	vid_meta['keywords'] 		= tree.xpath("//meta[@name='keywords']/@content")[0].split(',') 
	
	for k in prop_keys: 
		v = tree.xpath("//meta[@property='"+k+"']/@content") 
		vid_meta[prop_keys[k]] = v[0] if (len(v)> 0) else '' 

	for k in iprop_keys: 
		v = tree.xpath("//meta[@itemprop='"+k+"']/@content")
		vid_meta[iprop_keys[k]] = v[0] if (len(v)> 0) else '' 

	if (args != None):
		vid_meta['player_args'] 		= True 		# we don't quite need this but still! 
		for k in arg_keys: 
			vid_meta[k] = args[k] if (args.has_key(k)) else '' 

		vid_meta['country']	= args['cr'] 	if(args.has_key('cr')) else ''
		vid_meta['has_caption']	= True if vid_meta['caption_tracks'] != "" else False 
		f = args['fmt_list'].split(',')
		vid_meta['max_res'] 	= f[0].split('/')[1] if (f != None)  else 0 
		vid_meta['filesize'] 	= 0 	# right now we don't know 
	else :
		vid_meta['player_args'] = False 
		vid_meta['max_res'] 	= 0
		vid_meta['has_caption'] = False 
	
	return vid_meta 

def parse_stream_map(args):
	logr = logging.getLogger(vid) 

	encoded_map = args['url_encoded_fmt_stream_map'].split(",") if(args.has_key('url_encoded_fmt_stream_map')) else list() 
	encoded_map_adp = args['adaptive_fmts'].split(",") if(args.has_key('adaptive_fmts')) else list() 
	
	if( (len(encoded_map) ==0) and (len(encoded_map_adp) == 0)):
		logr.critical("Unable to find stream_map") 
		return None 

	res_index = {'small':'240','medium':'360','high':'480','large':'480','hd720':'720','1440p':'1440','1080p':'1080'} 

	fmt_stream_map = list()
	if (len(encoded_map) > 0) :
		for smap in encoded_map:
			if "&" not in smap:
				continue
			fmt_map_list = smap.split("&") 
			fmt_map = dict({'stream':"std", 'fps':"30"}) #Keep 30 fps as default. If the key exist, will be overwritten
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
        
		fmt_stream_map = sorted(fmt_stream_map, key= lambda k: (int(k['res'])+int(k['fps'])), reverse=True) 

	adp_stream_map_a = list()
	adp_stream_map_v = list()

	if (len(encoded_map_adp) > 0) :
		for smap in encoded_map_adp:
			if "&" not in smap :
				continue
			adp_map_list = smap.split("&") 
			adp_map = dict({'stream':"adp", 'fps':"30"}) #Keep 30 fps as default. If the key exist, will be overwritten
			for sm in adp_map_list:
				pair = sm.split("=")
				pair[1] = urllib.unquote(pair[1]).decode('utf8')
				pair[1] = urllib.unquote(pair[1]).decode('utf8')
				adp_map.update({str(pair[0]):str(pair[1])}) 
				if pair[0] == "quality":
					adp_map.update({'res':res_index[pair[1]]}) 
				if pair[0] == "size": 
					resw, resh = pair[1].split("x")
					adp_map.update({'res':int(resh)}) 
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
				
		adp_stream_map_v = sorted(adp_stream_map_v, key= lambda k: (int(k['res'])+int(k['fps'])), reverse=True) 
		adp_stream_map_a = sorted(adp_stream_map_a, key= lambda k: int(k['bitrate']), reverse=True) 

	caption_map = list() 
	if(args.has_key('caption_tracks')): 
		caption_str = args['caption_tracks'].split(",") 
		for cmap in caption_str:
			cap_map = dict() 
			cap = cmap.split("&")
			if(len(cap) < 2): 
				continue
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

	## ==== Attach all map variables ==============
	stream_map = dict() 
	stream_map['std']	= fmt_stream_map
	stream_map['adp_v']	= adp_stream_map_v
	stream_map['adp_a']	= adp_stream_map_a
	stream_map['caption'] 	= caption_map

	return stream_map 

def smap_to_str(s):
	if s['media'] == "audio-video":
		return '[%s] %s (%s);%s'%(s['media'],s['quality'],str(s['res']),s['type']) 
	if s['media'] == "video":
		return '[%s] %s (%s);%s'%(s['media'],s['quality_label'],str(s['size']),s['type']) 
	if s['media'] == "audio":
		return '[%s] %s kbps;%s'%(s['media'],int(s['bitrate'])/1024,s['type']) 
	if s['media'] == "caption":
		return '[%s] %s, %s :%s'%(s['media'],s['lang'],s['fmt'],s['name']) 
	
def ytmeta_load_vid(vid):
	logr = setup_item_logger(vid) 

	vid_meta = dict() 
	wpage = get_watch_page(vid) 	# wpage = watch_page
	if( (wpage['code'] != 200) or (wpage['len'] ==0) )  :	#only HTML code for success is 200 OK
		log.error("Can't Download item %s:Unable to fetch page. Response %d\nURL:%s",vid,watch_page['code'],watch_page['url']) 
		vid_meta['status'] = "NO_PAGE" 
		vid_meta['watch_page'] = wpage 
		return vid_meta
	else: 
		logr.debug("Got the watch page: %s [%d bytes]",wpage['url'],wpage['len']) 

	vid_meta =  parse_watch_page (wpage['contents'])	
	if(vid_meta['player_args'] == None):
		logr.error("Can't Download item %s:Unable to parse page or bad page",vid) 
		vid_meta['status'] = "BAD_PAGE" 
		return vid_meta

	vid_meta['stream_map'] =  parse_stream_map(vid_meta)	
	if not (vid_meta['stream_map']):
		logr.error("Can't Download item %s:Error parsing of the page",vid) 
		vid_meta['status'] = "NO_STREAMS"
		return vid_meta 

	print_pretty(logr,"Parsing successful: vid_meta "+"="*20,vid_meta) 

	vid_meta['status'] = "OK" 
	return vid_meta 


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
		print_smap_abridged("Selecting captions:caption_map",caption_map)
		print_smap_abridged("Selecting captions:select_map",select_map)
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


def download_caption(dlItem, folder):
	logr = logging.getLogger(vid) 

	title = clean_up_title(dlItem['title']) 
	uid = dlItem['vid'] 
	select_map = dlItem['select_map']
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


def download_streams(dlItem, folder):
	logr = logging.getLogger(vid) 

	title = dlItem['title'] 
	uid = dlItem['vid'] 
	select_map = dlItem['select_map']
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

	logr.info("\t[Outfile]: '%s'",outfile)

#---------------------------------------------------------------
# Top level functions for Main 

# dlItem should be a class! 
# dlItem should also have a better name
def download_item(vid,folder):
	logr = logging.getLogger(vid) 

	dlItem = ytmeta_load_vid(vid)

	if (dlItem['status'] != "OK"):
		return 

	smap = dlItem['stream_map']
	sm = smap['std'] + smap['adp_v'] + smap['adp_a'] + smap['caption'] 
	logr.debug("= Available Streams: "+"="*25+"\n"+"\n".join(map(smap_to_str,sm)))
	 
	dlItem['select_map'] = sl =  select_best_stream(smap) 
	logr.debug("= Selected Streams: "+"="*25+"\n"+"\n".join(map(smap_to_str,sl))+"\n")  

	# stream_map, select_map can be public elements so that they can be logged and print outside. 
	logr.info("\tTitle:'%s'\n\tAuthor:'%s'",dlItem['title'],dlItem['author'])  
	download_streams(dlItem,folder)	# TODO: this will only take dlItem in future 
	download_caption(dlItem,folder)
	logr.info("\tFetch Complete @ %s ----------------",str(datetime.datetime.now()))

	return

def download_list(url_list,folder) :
	logm = logging.getLogger() 
	
	i = 0
	for url in url_list:
		if( url['status'] == "OK"): 
			vid = url['id']
			logm.info("Downloading item %d %s : %s",i,url['id'],str(datetime.datetime.now()))
			download_item(url['id'],folder) 
			i += 1
		elif ((url['status'] == "SKIP") or (url['status'] == "ERROR")) : 
			logm.info("Download item %d [%s] : vid = %s : %s",i,url['status'],url['id'],"\t".join(url['attrs']) ) 
			i += 1
		else :
			logm.info("#%s",url['comment'])
	return

def read_list(listfile):
	i=0
	url_list = list() 
	lf  = open(listfile, "r")
	for line in lf:
		if line.strip():
			item = dict() 
			l = line.rstrip().split("#",1) 
			attrs = l[0].split('\t') 
			id_str = attrs[0] if(len(attrs) > 0) else "" 
			item["comment"] = l[1].strip() if(len(l) > 1) else "" 
			item["status"], item["id"] = get_vid_from_url(id_str) 
			item["attrs"] = attrs[1:] if (len(attrs)>0) else "" 
			url_list.append(item) 
		i += 1 

	return  url_list  

#---------------------------------------------------------------
# Support functions for Main 

def parse_arguments(argv): 
	logm = logging.getLogger() 
	usage_str = "Usage: %s -f|--folder='destination' -i|--item='id'/'watch_url' OR -l|--list='url_list'"
	vid = '' 
	item = ''
	ulist = '' 
	folder = ''
	list_mode = 0 

	try:
		opts, args = getopt.getopt(argv,"f:i:l:",["item=","list="])
	except getopt.GetoptError as err:
		logm.error("Error in Options: %s",str(err)) 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)
	
	if(len(opts) == 0): 
		logm.critical(usage_str,sys.argv[0])
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
		logm.warning("Missing destination folder. Assuming './' (current working directory) ") 
		folder = "./" 
	else:
		logm.debug("Destination folder for streams: %s",folder) 

	if ( item  == '' and ulist == '' ): 
		logm.critical("Missing source. Either supply item (id/url)  OR file with url_list") 
		logm.critical(usage_str,sys.argv[0])
		sys.exit(2)

	return folder, item, ulist, list_mode 

#---------------------------------------------------------------
# Main function

logm = setup_main_logger() 

(folder, item, ulist, list_mode) = parse_arguments(sys.argv[1:]) 
vid = '-'

if(list_mode == 1): 
	url_list = read_list(ulist) 
	logm.info("Downloading %d items from list %s",len(url_list),ulist) 
	download_list(url_list,folder) 
else:
	status, vid = get_vid_from_url(item)
	if(status == "OK") : 
		logm.info("Downloading item: [%s]",vid) 
		download_item(vid,folder) 
	else : 
		logm.info("Unable to download vid %s: %s",vid,status) 

logm.info("Good bye... Enjoy the video!") 

