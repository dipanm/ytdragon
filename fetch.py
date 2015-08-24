#!/usr/bin/python 

from lxml import html 
import requests 

import json
import urllib 
import pprint 

url = 'https://www.youtube.com/watch?v=kBCWl7qgwhw'
page = requests.get(url)
tree = html.fromstring(page.text) 
t = tree.xpath('//title/text()')
title = t[0].replace('\n','').strip()
print "Downloaded '"+title+"' -"+str(len(page.text))+" bytes"
#print "#####################################################"

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

arg_list = json.loads(player_script[p1:p2])
encoded_map = arg_list['args']['url_encoded_fmt_stream_map'].split(",") 
encoded_map_adp = arg_list['args']['adaptive_fmts'].split(",")

res_index = { 'small': '240', 'medium': '360', 'high': '480', 'hd720': '720' } 

count =0
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
	count+= 1

for smap in encoded_map_adp:
	fmt_map_list = smap.split("&") 
	fmt_map = dict({'fmt':"adp"}) 
	for sm in fmt_map_list:
		pair = sm.split("=")
		pair[1] = urllib.unquote(pair[1]).decode('utf8')
		pair[1] = urllib.unquote(pair[1]).decode('utf8')
		fmt_map.update({str(pair[0]):str(pair[1])}) 
		if pair[0] == "size": 
			res = str((pair[1].split("x"))[1])
			fmt_map.update({'res':res}) 

	if 'res' not in fmt_map:
		fmt_map.update({'res':'0'}) 
	fmt_stream_map.append(fmt_map)
	count+= 1

fmt_stream_map = sorted(fmt_stream_map, key= lambda k: int(k['res']), reverse=True) 

print "FINAL #####################################################"

for smap in fmt_stream_map:
	for key in smap:
		print key+":    "+str(smap[key])
	
	print "-----------------------------------" 

print "Good bye!" 

