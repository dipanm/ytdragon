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

def get_watch_page(url):
	page = requests.get(url)
	tree = html.fromstring(page.text) 
	t = tree.xpath('//title/text()')
	title = t[0].replace('\n','').rsplit('-',1)[0].strip() 

	parsed_url = urlparse.urlparse(url)
	vid = urlparse.parse_qs(parsed_url.query)['v'][0]

	print "=================================================================="
	print "Watch page:",url,"\n","Title:",title
	print "VID:",vid," Size:",len(page.text),"bytes"

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
	arg_list = json.loads(argstr)
	encoded_map = arg_list['args']['url_encoded_fmt_stream_map'].split(",") 
	encoded_map_adp = arg_list['args']['adaptive_fmts'].split(",")

	res_index = { 'small': '240', 'medium': '360', 'high': '480', 'hd720': '720', '1440p': '1440', '1080p': '1080'  } 

	print "Media stream options: Std:",len(encoded_map),"ADP:",len(encoded_map_adp)
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
				print "unknown media ...."+ media 
			
	adp_stream_map_v = sorted(adp_stream_map_v, key= lambda k: int(k['res']), reverse=True) 
	adp_stream_map_a = sorted(adp_stream_map_a, key= lambda k: int(k['bitrate']), reverse=True) 

	return { 'std': fmt_stream_map, 'adp_v': adp_stream_map_v, 'adp_a': adp_stream_map_a }

def print_smap_detailed(map_name,smap):
	print map_name,":",len(smap)," #############################################"
	i = 1; 
	for s in smap:
		print i,"-----------------------------------" 
		for key in sorted(s):
			print key,":    ",s[key]
		i += 1
		
def print_smap_abridged(map_name,smap):
	print map_name,"Total:  ",len(smap),"  ----------------------------------------------------- " 
	for s in smap:
		if s['media'] == "audio-video":
			print s['quality'],"("+str(s['res'])+"p)","[",s['type'],"]"
		if s['media'] == "video":
			print s['quality_label'],"(",s['size'],")","[",s['type'],"]"
		if s['media'] == "audio":
			print int(s['bitrate'])/1024,"kbps","[",s['type'],"]"

def print_stream_map_detailed(stream_map):
	print_smap_detailed("Standard",stream_map['std'])
	print_smap_detailed("ADP Video",stream_map['adp_v'])
	print_smap_detailed("ADP Audio",stream_map['adp_a'])
		
	
def print_stream_map_abridged(stream_map):
	print_smap_abridged("Standard",stream_map['std'])
	print_smap_abridged("ADP Video",stream_map['adp_v'])
	print_smap_abridged("ADP Audio",stream_map['adp_a'])


def dlProgress(count, blockSize, totalSize):
	if(totalSize > 0):
		percent = int(count*blockSize*100/totalSize)
	else: 
		percent = 0 

	count_p = totalSize/blockSize/100+1
	disp_interval = 5
	if(count == 0):
		print "Filesize",totalSize,"Bytes"
	if((count % (count_p*disp_interval) == 0) or (percent == 100)):
		print datetime.datetime.now(),":",percent,"% - ",(count*blockSize)/1000/1000,"of",(totalSize/1000/1000),"MB" 

def select_best_stream(stream_map):
	max_res_std = int(stream_map['std'][0]['res'])
	max_res_adp = int(stream_map['adp_v'][0]['res'])

	select_map = list(); 
	if(max_res_adp > max_res_std):
		select_map.append(stream_map['adp_v'][0]);
		select_map.append(stream_map['adp_a'][0]);
	else:
		select_map.append(stream_map['std'][0]);

	#select_map.append(stream_map['std'][0]);
	return select_map 

def download_streams(page, select_map,folder):
	title = page['title'] 
	uid = page['uid'] 

	separated = 1; 	# Assume sepeated content by default. If not, no need to merge 
	temp_files = dict(); 
	for smap in select_map:
		url = smap['url']
		media = smap['media']
		if(media == "audio-video"):
			filename = folder.rstrip('/')+"/"+str(title)+"-"+str(uid)+"."+str(smap['fmt'])
			separated = 0;
		else:
			filename = folder.rstrip('/')+"/"+str(uid)+"."+str(smap['media'])+"."+str(smap['fmt'])
			temp_files[media] = filename 


		print "\nDownloading ",smap['media'],": Destination=",filename
		print "URL: ",smap['url'],"\n"
		t0 = datetime.datetime.now() 
		#socket.setdefaulttimeout(60)
		fname, msg = urllib.urlretrieve(url,filename,reporthook=dlProgress) 
		t1 = datetime.datetime.now() 
		print "\n",msg,"Time ",t1-t0, "\n---------------------------------" 
	
	if(separated == 1):
		outfile = folder.rstrip('/')+"/"+str(title)+"-"+str(uid)+"."+str(smap['fmt'])
		cmd = "ffmpeg -y -i "+temp_files['video']+" -i "+temp_files['audio']+" -acodec copy \""+outfile+"\""
		print cmd 
		os.system(cmd)
		print "\nRemoving temp files"
		for key in temp_files:
			print key,"file:",temp_files[key]
			os.remove(temp_files[key]) 
		print "-----------------------------------" 

def download_stream(vid,folder):
	
	url = "https://www.youtube.com/watch?v="+vid

	watch_page = get_watch_page(url) 
	print "\n" 
	argstr =  get_stream_map_serial(watch_page['tree'])
	stream_map = parse_stream_map(argstr)

	#print_stream_map_detailed(stream_map)
	print_stream_map_abridged(stream_map)

	select_map = select_best_stream(stream_map) 
	print "\n" 
	print_smap_abridged("Selected",select_map)

	download_streams(watch_page,select_map,folder)

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
		print "Usage: ",sys.argv[0],"-f|--folder='destination' -i|--item='id'/'watch_url' OR -l|--list='url_list' "
		sys.exit(2)
	for opt, arg in opts:
		if opt in ("-f", "--folder"):
			folder = arg
			print "Destination folder", folder 
		elif opt in ("-i","--item"):
			item = arg 
			list_mode = 0 
		elif opt in ("-l","--list"):
			ulist = arg
			list_mode = 1 

	if ( folder == ''): 
		print "Missing destination folder. Assuming current working directory" 
		folder = "./" 

	if ( item  == '' and ulist == '' ): 
		print "Missing source. Either supply item (id/url)  OR file with url_list" 
		print "item=",item,"ulist=",ulist 
		print "Usage: ",sys.argv[0],"-f|--folder='destination' -i|--item='id'/'watch_url' OR -l|--list='url_list' "
		sys.exit(2)

	return folder, item, ulist, list_mode 

#---------------------------------------------------------------
# Main functions 

(folder, item, ulist, list_mode)   = parse_arguments(sys.argv[1:]) 

if(list_mode == 1): 
	url_list = read_list(ulist) 
	print "Downloading",len(url_list),"items from list",ulist 
	for url in url_list:
		vid = get_vid_from_url(url)
		download_stream(vid,folder)
else:
	print "Downloading one stream",item 
	vid = get_vid_from_url(item)
	download_stream(vid,folder)

print "Good bye... Enjoy the video!" 

