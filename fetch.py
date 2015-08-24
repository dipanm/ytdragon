#!/usr/bin/python 

from lxml import html 
import requests 

import json
import urllib 
import pprint 

url = 'https://www.youtube.com/watch?v=kBCWl7qgwhw'

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

	res_index = { 'small': '240', 'medium': '360', 'high': '480', 'hd720': '720' } 

	print "Total files: "+str(len(encoded_map)), str(len(encoded_map_adp))
	fmt_stream_map = list()
	for smap in encoded_map:
		fmt_map_list = smap.split("&") 
		fmt_map = dict({'fmt':"std"}) 
		for sm in fmt_map_list:
			pair = sm.split("=")
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			fmt_map.update({str(pair[0]):str(pair[1])}) 
			if pair[0] == "quality":
				fmt_map.update({'res':res_index[pair[1]]}) 
		
		fmt_stream_map.append(fmt_map)

	fmt_stream_map = sorted(fmt_stream_map, key= lambda k: int(k['res']), reverse=True) 

	adp_stream_map_a = list()
	adp_stream_map_v = list()
	for smap in encoded_map_adp:
		adp_map_list = smap.split("&") 
		adp_map = dict({'fmt':"adp"}) 
		for sm in adp_map_list:
			pair = sm.split("=")
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			pair[1] = urllib.unquote(pair[1]).decode('utf8')
			adp_map.update({str(pair[0]):str(pair[1])}) 
			if pair[0] == "quality":
				adp_map.update({'res':res_index[pair[1]]}) 
			if pair[0] == "size": 
				res = str((pair[1].split("x"))[1])
				adp_map.update({'res':res}) 
			if pair[0] == "type":
				media = (pair[1].split("/"))[0]

		if 'res' not in adp_map:
			adp_map.update({'res':'0'}) 
		if media == "video":
			adp_stream_map_v.append(adp_map)
		elif media == "audio":
			adp_stream_map_a.append(adp_map)
		else:
			print "unknown media ...."+ media 
			
	adp_stream_map_v = sorted(adp_stream_map_v, key= lambda k: int(k['res']), reverse=True) 
	adp_stream_map_a = sorted(adp_stream_map_a, key= lambda k: int(k['res']), reverse=True) 

	return { 'std': fmt_stream_map, 'adp_v': adp_stream_map_v, 'adp_a': adp_stream_map_a }

#---------------------------------------------------------------
# Main functions 

argstr =  get_stream_map_serial(url)

stream_map = parse_stream_map(argstr)

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
	
print "Good bye!" 

