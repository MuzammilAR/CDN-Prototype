#! /usr/bin/env python
import urllib2, SocketServer, SimpleHTTPServer, sys
from datetime import datetime
import hashlib
import os
import random, string
import threading
import signal
###########################################################
## GLOBAL VARIABLES
###########################################################
MEM_CACHE_DICT = {} # Note to self. since we store the reference to objects so we dont need to reassign 
DISK_CACHE_DICT = {} 
MEM_CACHE_LIMIT = 10 * 1024 * 1024   # 10 MB
DISK_CACHE_LIMIT = 10 * 1024 * 1024   # 10 MB
MEM_CACHE_TIMEOUT = 2 * 60  # 1 min 
DISK_CACHE_TIMEOUT = 7 * 60  # 5 min
MEM_CACHE_SIZE = 0
DISK_CACHE_SIZE = 0
MEM_CACHE_LOCK = threading.RLock() 
DISK_CACHE_LOCK = threading.RLock()
MEM_CACHE_SIZE_LOCK = threading.RLock() 
DISK_CACHE_SIZE_LOCK = threading.RLock()
DEPLOYED = False
###########################################################
# Lock order mem size, mem, disk size, disk

class MemCacheObject():
    def __init__(self, headers_dict, f_data, f_name, f_len = None, updtime = None):
        self.file_headers = headers_dict
        if f_len is None:
            f_len = len(f_data)
        if updtime is None:
            updtime = datetime.now()
        self.file_len = f_len
        self.file_name = f_name
        self.file_data = f_data
        self.last_modified = updtime
        self.num_count = 1
        
    def seenAgain(self):
        global DEPLOYED, MEM_CACHE_SIZE
        if not DEPLOYED:
            print "Cache found in Memory"
            print "Size: ", (MEM_CACHE_SIZE*1.0)/1024/1024
        self.last_modified = datetime.now()
        self.num_count += 1

    def createDiskCacheObject(self):
        x = DiskCacheObject(self.file_headers, self.file_data, self.file_name, self.file_len, self.last_modified)
        return x
        
        
class DiskCacheObject():
    def __init__(self, headers_dict, f_data, f_name, f_len = None, updtime = None):
        self.file_headers = headers_dict
        if f_len is None:
            f_len = len(f_data)
        if updtime is None:
            updtime = datetime.now()
        self.file_len = f_len
        self.last_modified = updtime
        self.file_name = f_name
        self.storage_name = None
        while self.storage_name is None: # just keep changing the name 
            try: # we are not creating a subdirectory. Bad idea but who care.
                self.storage_name = "cache_" + hashlib.md5(f_name).hexdigest()[:9]
            except:
                f_name += 5*random.choice(string.letters)   # add a random string
        f = open(self.storage_name, 'wb')
        f.write(f_data)
        f.close()
        self.num_count = 1
        
    def seenAgain(self):
        global DEPLOYED, DISK_CACHE_SIZE
        if not DEPLOYED:
            print "Cache found on Disk"
            print "Size: ", (DISK_CACHE_SIZE*1.0)/1024/1024

        self.last_modified = datetime.now()
        self.num_count += 1
        
    def getFile(self):
        f = open(self.storage_name,'rb')
        data = f.read()
        f.close()
        return data

    def createMemCacheObject(self):
        data = self.getFile()
        x = MemCacheObject(self.file_headers, data, self.file_name, self.file_len, self.last_modified)
        return x

def tryMovingFromDiskToMemory(diskCacheObject):
    global MEM_CACHE_TIMEOUT, MEM_CACHE_SIZE_LOCK, MEM_CACHE_SIZE, MEM_CACHE_LIMIT, MEM_CACHE_LOCK, MEM_CACHE_DICT, DISK_CACHE_LOCK, DISK_CACHE_DICT, DISK_CACHE_SIZE, DISK_CACHE_SIZE_LOCK
    # if there's space in memory, move it there.
    fName = diskCacheObject.file_name
    if MEM_CACHE_SIZE + diskCacheObject.file_len < MEM_CACHE_LIMIT:
        x = diskCacheObject.createMemCacheObject()
        addToMem(x)
        removeFromDisk(diskCacheObject)
        return True
    return False
        

def tryMovingFromMemoryToDisk(memCacheObject):
    global MEM_CACHE_SIZE_LOCK, MEM_CACHE_SIZE, MEM_CACHE_LIMIT, MEM_CACHE_LOCK, MEM_CACHE_DICT, DISK_CACHE_LOCK, DISK_CACHE_DICT, DISK_CACHE_SIZE, DISK_CACHE_LIMIT
    # if there's space in memory, move it there.
    fName = memCacheObject.file_name
    if DISK_CACHE_SIZE + memCacheObject.file_len < DISK_CACHE_LIMIT:
        x = memCacheObject.createDiskCacheObject()
        removeFromMem(memCacheObject)
        addToDisk(x)
        return True
    return False


def getMemObjectsAboveTimeout(curTime):
    global MEM_CACHE_TIMEOUT, MEM_CACHE_DICT
    removalList = []
    for k in MEM_CACHE_DICT:
        memCacheObject = MEM_CACHE_DICT[k]
        if (curTime - memCacheObject.last_modified).seconds > MEM_CACHE_TIMEOUT:
            removalList.append(memCacheObject)
    removalList.sort(key = lambda x: x.num_count)
    return removalList

def getDiskObjectsSortedOnTimeout():
    global DISK_CACHE_TIMEOUT, DISK_CACHE_DICT
    removalList = []
    for k in DISK_CACHE_DICT:
        diskCacheObject = DISK_CACHE_DICT[k]
        removalList.append(diskCacheObject)
    removalList.sort(key = lambda x: x.last_modified)
    return removalList

    
# we found something in disk but not in memory       
def cacheLogicFoundInDisk(diskCacheObject):
    global MEM_CACHE_TIMEOUT, MEM_CACHE_SIZE_LOCK, MEM_CACHE_SIZE, MEM_CACHE_LIMIT, MEM_CACHE_LOCK, MEM_CACHE_DICT, DISK_CACHE_LOCK, DISK_CACHE_DICT, DISK_CACHE_SIZE, DISK_CACHE_SIZE_LOCK
    # if there's space in memory, move it there.
    if tryMovingFromDiskToMemory(diskCacheObject):
        return None
    # otherwise
    curTime = datetime.now()
    lastSeenDiff = (curTime - diskCacheObject.last_modified).seconds
    if lastSeenDiff < MEM_CACHE_TIMEOUT:
        diskCacheObject.seenAgain()
        removalList = getMemObjectsAboveTimeout(curTime)
        # try compute the size of these things.
        removalListSize = 0
        diskAddList=[]
        for it in removalList:
            removalListSize += it.file_len
            diskAddList.append(it)
            if removalListSize >= diskCacheObject.file_len:
                break
        if removalListSize < diskCacheObject.file_len:
            pass # go for the count? miss karao yar. we'll decrease timer
        else:
            # write while loop remove thes from mem dic and add that thing to memdict.
            for k in diskAddList:
                removeFromMem(k)
            # move that object to mem
            tryMovingFromDiskToMemory(diskCacheObject)
            # move those to disk
            for k in diskAddList:
                tryMovingFromMemoryToDisk(k)
    else:
        diskCacheObject.seenAgain()
    # if last seen < memory time.
        # if there's space in memory add it and return.
        # if no space in memory, look at all the memory objects,
    # if last seen > memory time, call seenAgain
    return None


def removeFromDisk(diskCacheObject):    
    global DISK_CACHE_LOCK, DISK_CACHE_DICT, DISK_CACHE_SIZE
    with DISK_CACHE_LOCK:
        fName = diskCacheObject.file_name
        if fName in DISK_CACHE_DICT:
            del DISK_CACHE_DICT[fName]
            DISK_CACHE_SIZE -= diskCacheObject.file_len
            os.remove(diskCacheObject.storage_name)
    

def removeFromMem(memCacheObject):    
    global MEM_CACHE_LOCK, MEM_CACHE_DICT, MEM_CACHE_SIZE
    with MEM_CACHE_LOCK:
        fName = memCacheObject.file_name
        if fName in MEM_CACHE_DICT:
            del MEM_CACHE_DICT[fName]
            MEM_CACHE_SIZE -= memCacheObject.file_len

            
def addToDisk(diskCacheObject):
    global DISK_CACHE_LOCK, DISK_CACHE_DICT, DISK_CACHE_SIZE
    with DISK_CACHE_LOCK:
        fName = diskCacheObject.file_name
        DISK_CACHE_DICT[fName] = diskCacheObject
        DISK_CACHE_SIZE += diskCacheObject.file_len

        
def addToMem(memCacheObject):
    global MEM_CACHE_LOCK, MEM_CACHE_DICT, MEM_CACHE_SIZE
    with MEM_CACHE_LOCK:
        fName = memCacheObject.file_name
        MEM_CACHE_DICT[fName] = memCacheObject
        MEM_CACHE_SIZE += memCacheObject.file_len
        
    
def saveFileToCache(code, fName, fHeaders, fData):
    global MEM_CACHE_TIMEOUT, MEM_CACHE_SIZE_LOCK, MEM_CACHE_SIZE, MEM_CACHE_LIMIT, MEM_CACHE_LOCK, MEM_CACHE_DICT, DISK_CACHE_LOCK, DISK_CACHE_DICT, DISK_CACHE_SIZE, DISK_CACHE_SIZE_LOCK
    if code == '200': # most important line
        fLen = len(fData)
        if MEM_CACHE_SIZE + fLen < MEM_CACHE_LIMIT:
            memCacheObject =  MemCacheObject(fHeaders,fData, fName, fLen)
            with MEM_CACHE_LOCK:
                MEM_CACHE_DICT[fName] = memCacheObject
                MEM_CACHE_SIZE += fLen
            return None
        diskCacheObject =  DiskCacheObject(fHeaders,fData, fName, fLen)
        if DISK_CACHE_SIZE + fLen < MEM_CACHE_LIMIT:
            with DISK_CACHE_LOCK:
                DISK_CACHE_DICT[fName] = diskCacheObject
                DISK_CACHE_SIZE += fLen
            return None
        # new object. add to disk, and remove oldest objects.
        removalList = getDiskObjectsSortedOnTimeout()
        removalListSize = 0
        diskAddList=[]
        for it in removalList:
            removalListSize += it.file_len
            diskAddList.append(it)
            if removalListSize >= diskCacheObject.file_len:
                break
        # got all items to remove.
        #remove these items.
        for k in diskAddList:
            removeFromDisk(k)
        # add this item to disk
        addToDisk(diskCacheObject)
        
        
# cache algo.
# thread 1 runs every 2 minutes.        
def getFileFromCache(fName):
    # memory cache
    global MEM_CACHE_DICT
    global DISK_CACHE_DICT
    if fName in MEM_CACHE_DICT:
        memCacheObject = MEM_CACHE_DICT[fName]
        memCacheObject.seenAgain()
        return '200', memCacheObject.file_headers, memCacheObject.file_data
    # disk cache
    if fName in DISK_CACHE_DICT:
        diskCacheObject = DISK_CACHE_DICT[fName]
        # something to do with cache logic, found in disk but not mem
        t1 = threading.Thread(target=cacheLogicFoundInDisk, args=(diskCacheObject,))
        t1.daemon = True
        t1.start()        
        return '200', diskCacheObject.file_headers, diskCacheObject.getFile()
    return '404', None, None

            
def fetch_origin(full_url):
    try:
        f = urllib2.urlopen(full_url)
        headers = f.info().headers
        httpHeaders = {}
        for header in headers:
            if header.startswith('Content'):
                curHeader = header.split(': ')
                h = curHeader[0]
                p = curHeader[1].split("\r\n")[0]
                httpHeaders[h] = p
        return '200', httpHeaders, f.read()
    except urllib2.HTTPError, e:
        return str(e.code),{}, e.msg


def deleteCacheFilesOnDisk():
    print('Removing Cache Files from disk')
    filelist = [ f for f in os.listdir(".") if f.startswith("cache_") ]
    for f in filelist:
        os.remove(f)

        
def signal_handler(signal, frame):
    deleteCacheFilesOnDisk()
    print('Closing HTTP server')
    sys.exit(0)
        

class MyServer(SocketServer.TCPServer):
    def __init__(self, server_address, handler_class, original_server):
        SocketServer.TCPServer.__init__(self, server_address, handler_class)
        self.origin = original_server


class MyHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.protocol_version = 'HTTP/1.1'   # remove this and he if condition after for loop to remove http1.1
        code, headers, content = getFileFromCache(self.path)
        if content is None:
            resource_url = 'http://'+self.server.origin+':8080'+self.path
            code, headers, content = fetch_origin(resource_url)
            t1 = threading.Thread(target=saveFileToCache,args=(code, self.path, headers, content,))
            t1.daemon = True
            t1.start()
        # The cache found the response, either from the cache or fetched from origin
        if code == '200':
            self.send_response(200)
            for header in headers:
                self.send_header(header,headers[header])
            if "Content-Length" not in headers and "Content-length" not in headers:  #remove me to remove http1.1  
                self.send_header("Content-Length", len(content))
            self.end_headers()
            # write the original content back
            self.wfile.write(content)
        else:
            self.send_response(int(code))
            self.end_headers()
            self.wfile.write(content)
            print resource_url, code, content
            
            
def checkArgs(args):
    try:
        if '-p' in args:
            port = args[args.index('-p')+1]
            args.remove('-p')
            args.remove(port)
            port=int(port)
        if '-o' in args:
            origin = args[args.index('-o')+1]
            args.remove('-o')
            args.remove(origin)
        return port, origin
    except:
        print 'Please provide the parameters as specified: -p <port> -o <origin>'
        sys.exit()

def main(argv):
    signal.signal(signal.SIGINT, signal_handler)
    # The server will be running on this port
    # and it will contact original server for content
    port, oriServer= checkArgs(argv)
    #HTTP handler
    Handler = MyHandler
    #The real http server with he handler
    httpd = MyServer(("", port), Handler,oriServer)

    print "serving at port", port
    httpd.serve_forever()

if __name__=="__main__":
    main(sys.argv)
