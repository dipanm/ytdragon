import os
import sys
import logging
import datetime
import socket
import urllib
import requests
from ytdragon.utils import print_pretty

# when we shall replace this method by class:
# vid and totalSize will be set only once in begining; count will be internal
# once monitor is a class, it will also measure start time and current time to calculate effective bit rate.
#  - instantaneous or gross bit rate? some algo needed.
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
        self.block_size = 1024*1024

    def get_stream(self,smap_string,url,filename):

        self.logr.info("\t%s",smap_string)
        self.logr.debug("\tSaving URL: %s\n\tto %s",url,filename)
        t0 = datetime.datetime.now()
        socket.setdefaulttimeout(120)
        #print("\n--------\n",url,"\n--------\n")

        # Begin Request
        r = requests.get(url, stream=True)
        print_pretty(self.logr,"Headers:",r.headers)

        # Check if the file already exist
        filesize = int(r.headers['Content-Length'])
        current_size = os.path.getsize(filename) if os.path.isfile(filename) else 0
        if(current_size == filesize):
            self.logr.info("\tFile already exist size:{}".format(current_size))
            return

        # do this only if status = 200OK
        count = 0
        actual_size = 0
        with open(filename, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=self.block_size):
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
