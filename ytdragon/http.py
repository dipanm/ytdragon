import sys
import logging
import datetime
import socket
import urllib
import requests

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

        r = requests.get(url, stream=True)
        filesize = int(r.headers.get('content-length'))
        self.logr.info("Status:{} Content-Type:{} TotalSize:{}".format(r.status_code,r.headers['Content-Type'],filesize))

        # do this only if status = 200OK
        received = 0
        actual_size = 0
        block_size = 1024*1024
        with open(filename, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=block_size):
                if chunk:
                    actual_size += len(chunk)
                    fd.write(chunk)
                    received += 1
                    dlProgress(received, block_size, filesize)
                else:
                    break
                    self.logr.info("\nFile download complete size:received {}\n".format(actual_size))

        #fname, msg = urllib.request.urlretrieve(url,filename,reporthook=dlProgress)
        t1 = datetime.datetime.now()
        sys.stdout.write("\r")
        sys.stdout.flush()
        self.logr.debug("Time taken %s\n---------------------------------",str(t1-t0))

        return
