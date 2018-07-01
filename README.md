# ytdragon
A Dragon among all the Youtube Downloaders!

This is a commandline application that helps you download *lots* of videos from various sites.
So far we have mastered to work with Youtube, but more is on the way! 

The _KISS_ principle: Keep it simple, stupid! 
Make easier things _really_ easy, and even difficult things painless! 

Use Case #1: Download single Video, Playlist, full channel or user. 
========================================================================
At the outset, this tool allows you to download video as follows:

fetch.py -f "folder-name" _ref_ 

* _ref_ can be a full URL, or it can be a uniqe id such as yt.vid=id  
In all above cases: 'yt' stands for 'youtube'. 

Examples: 

A. "ref" can be simply a URL. 
So download single video with:  fetch.py https://www.youtube.com/watch?v=OHw80HXSuAQ
Or the playlist as follows: 	fetch.py https://www.youtube.com/playlist?list=PLZrSPiD-ZQr16Z3omGzzeSCdz-m7eaO2W  
Or the full user videos' as:	fetch.py https://www.youtube.com/user/makemegenius
Or the complete channel like: 	fetch.py https://www.youtube.com/

B. "ref" can be specified through an id. For example, 
Download the above video using:	 fetch.py yt.vid=OHw80HXSuAQ 
Download the above playlist as:  fetch.py yt.pl=PLZrSPiD-ZQr16Z3omGzzeSCdz-m7eaO2W
Download the above user with:    fetch.py yt.user=makemegenius
Download the above channel by:   fetch.py yt.ch=

Power of simplicity: 
------------------------------------------------------------------------
* The ytdragon will generate a good name with title_-_id.ext on its own. Later will allow user to specify this as well. But idea is, not to bother people with keep on writing extra names, and as you generate your collection, it helps having unified name. 
* Which format? - well ytdragon will simply download the best possible format, i.e. highest quality by default. 
* No restrictions of formats. Unlike many downloaders, downloading 1080p or 480p due to adaptive streaming, is no issue. Ytdragon fgures out automatically best combination and seamlessly stiches (muxes) it. 
* By default, it will also bring ('en') subtitles (.srt files), sitting in the same folder with same-name.srt 

Use Case #2: Create a simple list and download the full thing:
========================================================================

Here the power begins. As you surf the net, you don't wait for individual downloads. 
Just decide which ones you want. you can make a file named such as "mydownload.yl"  
Just open any of your favorite editor and keep collecting the URL. 

The format is not at atll complicated.
A typical simple file can just be any _ref_, one in each line. 
The ref can be either a Video URL,  yt.vid=_id_ format. 
The list need not be from a single user, playlist or channel. It can be a set of any valid _ref_ 

The list can be any long as you want.

Once done fire the fetch command: fetch.py yl=modownload.yl 

Just leave it and you get your content. 

Use Case #3: Manage downloads: 
========================================================================

Sometimes we search for many videos, may be a for quite a few days. We might be looking for full series and get episodes not from one user, but scattered around. So keep adding refs and begin organizing them. 

There are quite a few things you you can do with .yl files. 

A. Overtime, we don't recollect which ref/id corresponds to which videos - so apart from _ref_ you can write a small comment for example 
 ``yt.vid=OHw80HXSuAQ  # educational - newton's law! ``

B. You can make simple sections say for different subjects/topics, or different series etc. by leaving lines - and having full lines as comments. For example:
``#------- Pysics -----------------
  http://www.youtube.com/watch?v=OHw80HXSuAQ
  yt.vid=DNbjL8gr1iM
  
  #------  Chemistry --------------
  yt.vid=xyZabc 
``

Use Case #4: Extrect metadat : 
========================================================================

While it is possible to simply fetch the playlist, or channel or user using _fetch_ script, it might be important to first review the full list, before jumping the gun.  Specifically, you can extract the full metadata before you begin to download. 

Here is how you do it: 
   ``extract.py [-o|--outfile="outfilename"] <list_ref>``
   The output file can be separate if you wish. Else it will be over written.

* Metadata extraction only works for list right now! may be it should work for individual videos as well! (TODO). 
* So it can be a playlist, channel or user on the site. OR it can also be one of the "mydownloads.yl" files as well. 
* Extract identifies length (duration) and quality of the video, name of the author and other flags. 

Once you extract these listes - you can download the content through list: ``fetch yl=list.yl`` 

There are number of reasons, you might want to 
------------------------------------------------------------------------
* No need to keep scrolling long playlists manually. 
* Many long playlists have duplicate videos, i.e. same video added twice in the same list. You can avoid downloading this again.
* Many a times a video is added in playlist, but later the video is deleted, or has restricted. Clean this.
* The fully extracted list shows you in the header how many were duplicate, deleted and erroneous and how many uniques.
* Specifically, checking on every video on youtube whether it is good quality or not, is quite pain. 
* So sometimes you only want to download videos which are of proper length (not cut out), or only ones with good quality. 
 

Use Case #5: Download selectively: 
========================================================================

This usecase is only limited so far. For now, after examining the content though extract, you can comment out all those which you don't want to download by simply putting a comment on the start of the line. 

* You can re-order the list as per priority, just by moving around URLs, or sections. 
* You can identify which is the 'best-quality' video of the same series/episode and delete or comment out the ones which is not required. 
* You can curate your playlists by series/episodes or specfic authors so that all of them can be downloaded separately in their individual folder. 

More sophistication is required where you can enable/disable whole sections.  
In future release, downloads once done will be automatically be skipped so you may keep downloading over multiple sessions. 


Other things:
========================================================================

Why command line?
------------------------------------------------------------------------
* Command line is _home_ for the geeks. Its rather most natural to work out using commandline rather than over GUI.
* Many download managers are essentilly browser based and as you keep downloading many videos from different pages, following references or lists and so on, your browser keeps getting bloated wth memory.
* With GUI, we are generally bound with it. Add one by one and wait for things to happen. Instead, here just collect what all things you want to download, in a nice file and make it work. 
* Run in the background, on the server, or write scripts to automate stuff - things that can't be done via GUI. 
* Last but not the least, edit all your .yl files in vi or your favorite editor - no need to learn new complicated interface! 

Why not just use URL? Why _ref_ ? 
------------------------------------------------------------------------
* It begun with just a URL, but as we included (yl) list, and may be other things that will come in way, _ref_ is rather generic way.
* As .yl files begun to become bigger for me, I realized, that keeping id and removing all other redundent part of URL becomes clumsy.
- hence keeping _ref_ makes it easier



Though, this is just a beginning. 

Do use it. Do give your comments - and wish list ideas. 


