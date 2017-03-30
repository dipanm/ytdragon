#!/usr/bin/python -u 

from lxml import html 

import json
import urllib
import re
import urlparse

from ytutils import print_pretty
from ytpage import get_page

### User Config Variable ----------------------------

default_host = "youtube.com" 
default_hurl = "https://"+default_host 

#------ Exception Handling class -----------------------------------------------
class ytd_exception_meta(Exception): 
	error_table = { "PAGE_FETCH_ERR": "Can't fetch watch page", 
			"YOUTUBE_ERROR"	: "Youtube Can't serve this page!", # Raised in parse_watch_page() 
			"BAD_PAGE" 	: "Unable to parse page or illformed page", 
			"NO_STREAMS" 	: "Download stream_map not available" }   
			
	def __init__(self,error,page,meta,extra_msg): 
		self.errtype	= error
		self.errmsg	= self.error_table[error] if self.error_table.has_key(error) else "Unknown" 
		self.page	= page
		self.vidmeta	= meta
		self.msgstr 	= extra_msg


##--- support functions -------------------------------------------------------
def smap_to_str(s):
	if s['media'] == "audio-video":
		return '[%s] %s (%s);%s'%(s['media'],s['quality'],str(s['res']),s['type']) 
	if s['media'] == "video":
		return '[%s] %s (%s);%s'%(s['media'],s['quality_label'],str(s['size']),s['type']) 
	if s['media'] == "audio":
		return '[%s] %s kbps;%s'%(s['media'],int(s['bitrate'])/1024,s['type']) 
	if s['media'] == "caption":
		return '[%s] %s, %s :%s'%(s['media'],s['lang'],s['fmt'],s['name']) 
	
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

def fast_extract_fmt_list(script_str) :
	p1 = script_str.find("\"fmt_list\":") 
	val= script_str[p1:].split(":")[1].split(",")[0]
	max_res	= val.split('\/')[1] if (len(val) >0 )  else 0 
	return max_res 

#------ Page fetch and parsing - called by load_vid_meta -----------------------

def parse_watch_page(wpage):

	page = wpage['contents'] 
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
		plerror = " ".join(map(str.strip, tree.xpath('//div[@id="player-unavailable"]//text()'))) 
		raise ytd_exception_meta("YOUTUBE_ERROR",wpage,vid_meta,plerror) 

	# extract player args from the player script 	
	arg_list = json.loads(player_script)
	args = arg_list['args'] if arg_list.has_key('args') else None 

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

def parse_watch_page_express(wpage):

	page = wpage['contents'] 
	prop_keys = { 'og:title' : 'title' , 'og:type' : 'type' }
	iprop_keys = { 'videoId' : 'vid' , 'genre': 'genre', 'isFamilyFriendly': 'isFamilyFriendly','paid': 'paid' }

	vid_meta = dict() 
	# extract dom tree of HTML Page
	tree = html.fromstring(page) 

	# extract player script 
	script = tree.xpath('//script[contains(.,"ytplayer")]/text()') 
	vid_meta['max_res'] = fast_extract_fmt_list(script[0])	if (len(script) > 0) else 0 

	# populate the attributes
	vid_meta['author'] 		= " ".join(map(str.strip, tree.xpath("//div[@class='yt-user-info']//text()"))).strip()
	
	for k in prop_keys: 
		v = tree.xpath("//meta[@property='"+k+"']/@content") 
		vid_meta[prop_keys[k]] = v[0] if (len(v)> 0) else '' 

	for k in iprop_keys: 
		v = tree.xpath("//meta[@itemprop='"+k+"']/@content")
		vid_meta[iprop_keys[k]] = v[0] if (len(v)> 0) else '' 

	vid_meta['player_args'] = False 
	
	return vid_meta 


def parse_stream_map(args):

	encoded_map = args['url_encoded_fmt_stream_map'].split(",") if(args.has_key('url_encoded_fmt_stream_map')) else list() 
	encoded_map_adp = args['adaptive_fmts'].split(",") if(args.has_key('adaptive_fmts')) else list() 
	
	if( (len(encoded_map) ==0) and (len(encoded_map_adp) == 0)):
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

#---- The primary API function: -----------------------------------------------
#	load_video_meta() 

def load_video_meta(vid,express=False):

	vid_meta = dict() 
	wpage = get_page("video",vid) 	# wpage = watch_page
	if( (wpage['code'] != 200) or (wpage['len'] ==0) )  :	#only HTML code for success is 200 OK
		raise ytd_exception_meta("PAGE_FETCH_ERR",wpage,vid_meta,"HTTP Error Code-{}".format(wpage['code']) ) 

	if express: 
		vid_meta =  parse_watch_page_express (wpage)
		return vid_meta

	else : 
		vid_meta =  parse_watch_page (wpage)
		if(vid_meta['player_args'] == None):
			raise ytd_exception_meta("BAD_PAGE",wpage,vid_meta,"") 
        
		vid_meta['stream_map'] =  parse_stream_map(vid_meta)	
		if not (vid_meta['stream_map']):
			raise ytd_exception_meta("NO_STREAMS",wpage,vid_meta,"") 
        
		return vid_meta 


