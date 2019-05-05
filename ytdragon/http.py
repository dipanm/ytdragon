import sys
import logging
import datetime
import socket
import urllib

def dlProgress(count, blockSize, totalSize):
        #global vid
        #logm = logging.getLogger()
        #logr = logging.getLogger(vid)

        counter_str = [ "|","/","-","\\"]
        cstr = counter_str[(int(count/100))%4]

        if(totalSize > 0):
                percent = int(count*blockSize*100/totalSize)
        else:
                percent = 0

        count_p = totalSize/blockSize/100+1
        disp_interval = 5
        """
        if(count == 0):
                logr.debug("Filesize %d Bytes",totalSize)
        if(totalSize > 1000*1000):
                if((count % (count_p*disp_interval) == 0) or (percent == 100)):
                        tnow = datetime.datetime.now()
                        logr.debug("%s : %d%% - %d of %d MB",str(tnow),percent,(count*blockSize)/1000/1000,(totalSize/1000/1000))
        """

        sys.stdout.write("\r\tDownload progress: %s %d%% of %d MB " % (cstr,percent, totalSize/1000/1000) )
        sys.stdout.flush()


class DlHttp:

    def __init__(self,vid):
        self.logr = logging.getLogger(vid)

    def get_stream(self,smap_string,url,filename):

        self.logr.info("\t%s",smap_string)
        self.logr.debug("\tSaving URL: %s\n\tto %s",url,filename)
        t0 = datetime.datetime.now()
        socket.setdefaulttimeout(120)
        #print("\n--------\n",url,"\n--------\n")
        fname, msg = urllib.request.urlretrieve(url,filename,reporthook=dlProgress)
        t1 = datetime.datetime.now()
        sys.stdout.write("\r")
        sys.stdout.flush()
        self.logr.debug("%sTime taken %s\n---------------------------------",msg,str(t1-t0))

        return
