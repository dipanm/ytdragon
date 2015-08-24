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

print "#####################################################"

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

argstr = player_script[p1:p2] 
print p1, p2, nesting
print "#####################################################"

arg_list = json.loads(argstr)
encoded_fmt_stream_map = arg_list['args']['url_encoded_fmt_stream_map']
smap_list = encoded_fmt_stream_map.split(",") 

encoded_map = arg_list['args']['url_encoded_fmt_stream_map'].split(",") 

#print url_map 
#print "#####################################################"

count =0
fmt_stream_map = list()
for smap in smap_list:
	fmt_map_list = smap.split("&") 
	smap = dict() 
	for sm in fmt_map_list:
		pair = sm.split("=")
		pair[1] = urllib.unquote(pair[1]).decode('utf8')
		pair[1] = urllib.unquote(pair[1]).decode('utf8')
		smap.update({pair[0]:pair[1]}) 

	fmt_stream_map.append(smap)
	count+= 1

print "FINAL #####################################################"
#pprint.pprint(fmt_stream_map)

for smap in fmt_stream_map:
	print "-----------------------------------" 
	for key in smap:
		print key+":\t\t"+smap[key]


