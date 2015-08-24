#!/usr/bin/python 

from lxml import html 
import requests 

import json
import urllib 
import pprint 

#url = 'https://www.youtube.com/watch?v=kBCWl7qgwhw'
url = 'https://www.youtube.com/watch?v=HoO10EIyrMo'

def get_stream_map_serial(url):
	page = requests.get(url)
	tree = html.fromstring(page.text) 
	t = tree.xpath('//title/text()')
	title = t[0].replace('\n','').strip()
	print "Downloaded '"+title+"' -"+str(len(page.text))+" bytes"

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

	print "Total files: "+str(len(encoded_map)), str(len(encoded_map_adp))
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


def print_sream_map(stream_map):
	print "STANDARD "+ str(len(stream_map['std'])) + " #############################################"
	for smap in stream_map['std']:
		for key in sorted(smap):
			print key+":    "+str(smap[key])
		print "-----------------------------------" 
		
	print "ADP Video "+ str(len(stream_map['adp_v'])) + " ###########################################"
	for smap in stream_map['adp_v']:
		for key in sorted(smap):
			print key+":    "+str(smap[key])
		print "-----------------------------------" 
		
	print "ADP Audio "+ str(len(stream_map['adp_a'])) + " ###########################################"
	for smap in stream_map['adp_a']:
		for key in sorted(smap):
			print key+":    "+str(smap[key])
		print "-----------------------------------" 
	
#---------------------------------------------------------------
# Main functions 

argstr =  get_stream_map_serial(url)
stream_map = parse_stream_map(argstr)
#print_sream_map(stream_map)

max_res_std = int(stream_map['std'][0]['res'])
max_res_adp = int(stream_map['adp_v'][0]['res'])

select_map = list(); 
if(max_res_adp > max_res_std):
	select_map.append(stream_map['adp_v'][0]);
	select_map.append(stream_map['adp_a'][0]);
else:
	select_map.append(stream_map['std'][0]);

print "Max resolution: " +str(max_res_std), str(max_res_adp)

print "Selected: #########################################################" 
for smap in select_map:
	for key in sorted(smap):
		print key+":    "+str(smap[key])
	print "-----------------------------------" 

print "Good bye!" 

