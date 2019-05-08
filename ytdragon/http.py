import sys
import logging
import datetime
import socket
import urllib
import requests
from ytdragon.utils import print_pretty

def dlProgress(vid, count, actual_size, totalSize,last=False):
        logm = logging.getLogger()
        logr = logging.getLogger(vid)

        percent = int(actual_size*100/totalSize) if(totalSize > 0) else 0

        counter_str = [ "|","/","-","\\"]
        cstr = counter_str[(int(count))%4]

        if(count == 0):
                logr.debug("Filesize %d Bytes",totalSize)
        if( (actual_size == totalSize) or last):
                tnow = datetime.datetime.now()
                logr.debug("%s : %d%% - %d of %d MB",str(tnow),percent,(actual_size)/1000/1000,(totalSize/1000/1000))

        sys.stdout.write("\r\tDownload progress: %s %d%% of %d MB " % (cstr,percent, totalSize/1000/1000) )
        sys.stdout.flush()


class DlHttp:

    def __init__(self,vid):
        self.vid = vid
        self.logr = logging.getLogger(vid)

    def get_stream(self,smap_string,url,filename):

        self.logr.info("\t%s",smap_string)
        self.logr.debug("\tSaving URL: %s\n\tto %s",url,filename)
        t0 = datetime.datetime.now()
        socket.setdefaulttimeout(120)
        #print("\n--------\n",url,"\n--------\n")

        # Begin Request
        r = requests.get(url, stream=True)
        filesize = int(r.headers['Content-Length'])
        print_pretty(self.logr,"Headers:",r.headers)

        # do this only if status = 200OK
        count = 0
        actual_size = 0
        block_size = 1024*1024
        with open(filename, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=block_size):
                if chunk:
                    actual_size += len(chunk)
                    fd.write(chunk)
                    count += 1
                    dlProgress(self.vid,count,actual_size,filesize)
                else:
                    break
                    self.logr.info("\nFile download complete size:received {}\n".format(actual_size))

        t1 = datetime.datetime.now()
        sys.stdout.write("\r")
        sys.stdout.flush()
        self.logr.debug("Time taken %s\n---------------------------------",str(t1-t0))

        return
