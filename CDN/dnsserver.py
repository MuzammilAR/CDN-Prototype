#! /usr/bin/env python
import socket
import threading
import SocketServer
import sys,time, subprocess, os
import random
import signal
import struct
import traceback
from geopy import distance as geo_distance
from geoloc import search_ipinfoio as ipinfo
from geoloc import other_geo_sources as eurek_dbip
from expiringdict import ExpiringDict
# write a thread that cleans CLIENT_DICTs for every client not seen for more than 5 minutes. all of them.

USERNAME = "fangfanli"
KEYFILE = "~/.ssh/id_rsa"
HOST = "cs5700cdnproject.ccs.neu.edu"
PORT = random.randint(40000, 65535)
CDN_SPECIFIC_NAME = "cs5700cdn.example.com"
ORIGIN_SERVER = "ec2-54-88-98-7.compute-1.amazonaws.com"
DEPLOYED = False
DNS_RECORDS_DICT = {'ec2-52-29-65-165.eu-central-1.compute.amazonaws.com': '52.29.65.165', 'ec2-52-38-67-246.us-west-2.compute.amazonaws.com': '52.38.67.246', 'ec2-54-233-185-94.sa-east-1.compute.amazonaws.com': '54.233.185.94', 'ec2-52-63-206-143.ap-southeast-2.compute.amazonaws.com': '52.63.206.143', 'ec2-54-85-32-37.compute-1.amazonaws.com': '54.85.32.37', 'ec2-52-196-70-227.ap-northeast-1.compute.amazonaws.com': '52.196.70.227', 'ec2-54-193-70-31.us-west-1.compute.amazonaws.com': '54.193.70.31', 'ec2-54-169-117-213.ap-southeast-1.compute.amazonaws.com': '54.169.117.213', 'ec2-52-51-20-200.eu-west-1.compute.amazonaws.com': '52.51.20.200'}
DNS_RECORD_LOCATION_DICT = {'ec2-52-29-65-165.eu-central-1.compute.amazonaws.com': {'lat': 50.1167, 'lon': 8.6833}, 'ec2-52-38-67-246.us-west-2.compute.amazonaws.com': {'lat': 45.7788, 'lon': -119.529}, 'ec2-54-233-185-94.sa-east-1.compute.amazonaws.com': {'lat': -23.5475, 'lon': -46.6361}, 'ec2-52-63-206-143.ap-southeast-2.compute.amazonaws.com': {'lat': -33.8678, 'lon': 151.2073}, 'ec2-54-85-32-37.compute-1.amazonaws.com': {'lat': 39.0335, 'lon': -77.4838}, 'ec2-52-196-70-227.ap-northeast-1.compute.amazonaws.com': {'lat': 35.685, 'lon': 139.7514}, 'ec2-54-193-70-31.us-west-1.compute.amazonaws.com': {'lat': 37.3394, 'lon': -121.895}, 'ec2-54-169-117-213.ap-southeast-1.compute.amazonaws.com': {'lat': 1.2931, 'lon': 103.8558}, 'ec2-52-51-20-200.eu-west-1.compute.amazonaws.com': {'lat': 53.3331, 'lon': -6.2489}}
CLIENT_GEOLOC_DICT = {}
CLIENT_ACTIVE_MEASUREMENTS_DICT = {}
CLIENT_PASSIVE_MEASUREMENTS_DICT = {}
LOCK_GEOLOC_DICT = threading.RLock() # we use the same lock for read and write. we can get away with reading without the lock but always write with the lock
LOCK_ACTIVE_DICT = threading.RLock() # we use the same lock for read and write. we can get away with reading without the lock but always write with the lock
LOCK_PASSIVE_DICT = threading.RLock() # we use the same lock for read and write. we can get away with reading without the lock but always write with the lock
# ACTIVE_CLIENT_DICT is an expiringDictionary keyed by the client ip addresses, the entries will be expired after the timeout if it is not renewed during the period
ACTIVE_CLIENT_DICT = ExpiringDict(max_len=30, max_age_seconds=200)

class DNSPacket():
    def __init__(self):
        self.query_id = 0
        self.qr = 0
        self.opcode = 0
        self.aa = 0
        self.tc = 0
        self.rd = 0
        self.ra = 0
        self.bitcodes = 0
        self.z_value = 0
        self.rcode = 0
        self.question_count = 0
        self.answer_count = 0
        self.authority_count = 0
        self.add_rec_count = 0
        self.questions = []
        self.answers = []
        self.authority = []
        self.add_record = []
        self.return_error = False

    def parsePacket(self, data):
        try:
            (self.query_id, bit_codes, self.question_count,
                self.answer_count, self.authority_count,
                self.add_rec_count) = struct.unpack("!HHHHHH",
                data[0:12])   # the first 6H. we'll  handle     print x
            self.bitcodes = bit_codes
            self.rcode = bit_codes & 0xF
            bit_codes = bit_codes >> 4
            self.z_value = bit_codes & 0x7
            bit_codes = bit_codes >> 3
            self.ra = bit_codes & 0x1
            self.rd = ((bit_codes >> 1) & 0x1)
            self.tc = ((bit_codes >> 2) & 0x1)
            self.aa = ((bit_codes >> 3) & 0x1)
            bit_codes = bit_codes >> 4
            self.opcode = bit_codes & 0xF
            bit_codes = bit_codes >> 4
            self.qr = bit_codes & 0x1
            data = data[12:]
            # read question, only first one.
            q = ""
            num_oct_q = struct.unpack("!B", data[0])
            num_oct_q = num_oct_q[0]
            data = data[1:]
            while num_oct_q > 0:
                formt = ''.join(["c" for x in xrange(num_oct_q)])
                formt = "!" + formt
                x = struct.unpack(formt, data[0:num_oct_q])
                q += ''.join(x)
                data = data[num_oct_q:]
                num_oct_q = struct.unpack("!B", data[0])
                num_oct_q = num_oct_q[0]
                if num_oct_q > 0:
                    q += "."
                data = data[1:]
            # set rcode to 3 if anything but A or IN.
            q_type, q_class = struct.unpack("!HH", data[0:4])
            if q_type != 1:
                self.rcode = 3
            if q_class != 1:
                self.rcode = 3
            #print q_class,q_type
            self.questions.append((q, q_type, q_class))
        except:
            print "Malformed packet"
            self.rcode = 1

    def addAnswer(self, ttl, ip):
        self.answer_count = 1
        ans = (1, 1, ttl, 4, ip)
        self.answers.append(ans)

    def createResponse(self):
        # response bit
        self.qr = 1
        # set recursion allowed.
        self.ra = 1
        # not rec desired
        self.rd = 0
        # no additional section
        self.add_rec_count = 0
        bit_codes = (self.qr << 15) | ((self.opcode & 0xF) << 11) | (self.aa << 10) | (self.tc << 9) | (self.rd << 8) | (self.ra << 7) | (self.z_value << 4) | self.rcode
        packet = struct.pack("!HHHHHH",
            self.query_id, bit_codes, self.question_count, self.answer_count,
            self.authority_count, self.add_rec_count)
        # now add the question
        for curQuestionTuple in self.questions:
            curQuestion = curQuestionTuple[0]
            curQList = curQuestion.split('.')
            for curStr in curQList:
                curLen = len(curStr)
                packet += struct.pack("!B", curLen)
                for x in curStr:
                    packet += struct.pack("!c", x)
            packet += struct.pack("!B", 0)
            packet += struct.pack("!HH", curQuestionTuple[1],
                curQuestionTuple[2])
        for answerTuple in self.answers:
            ptr = 0xC
            ptrOff = 0xC
            nme = (ptr << 12) | ptrOff
            #(1, 1, ttl, 4, ip)
            ip_addr = socket.inet_aton(answerTuple[4])
            packet += struct.pack("!HHHIH4s", nme, answerTuple[0],
                answerTuple[1], answerTuple[2], answerTuple[3], ip_addr)
        # answer pointer: hardcoded since only one question
        return packet


# this function should be modified for DNS redirection.
def getCNameAndIPAddress(ip):
    # k is the cname and v is the ip address
    k, v = getCNameAndIPAddressActive(ip)
    if k is None:
        k, v = getCNameAndIPAddressPassive(ip)
    if k is None:
        k, v = getCNameAndIPAddressGeoloc(ip)
    if k is None:
        k, v = getCNameAndIPAddressDefault()
    return k, v

def getCNameAndIPAddressPassive(ip_addr):
    return None, None

# This is used to call scamper on every replica for given client ip
# Then update CLIENT_ACTIVE_MEASUREMENTS_DICT based on the active measurement result
def active_measure(client_ip):
    global CLIENT_ACTIVE_MEASUREMENTS_DICT
    global USERNAME
    global KEYFILE

    replicas = ['ec2-54-85-32-37.compute-1.amazonaws.com',
                'ec2-54-193-70-31.us-west-1.compute.amazonaws.com',
                'ec2-52-38-67-246.us-west-2.compute.amazonaws.com',
                'ec2-52-51-20-200.eu-west-1.compute.amazonaws.com',
                'ec2-52-29-65-165.eu-central-1.compute.amazonaws.com',
                'ec2-52-196-70-227.ap-northeast-1.compute.amazonaws.com',
                'ec2-54-169-117-213.ap-southeast-1.compute.amazonaws.com',
                'ec2-52-63-206-143.ap-southeast-2.compute.amazonaws.com',
                'ec2-54-233-185-94.sa-east-1.compute.amazonaws.com']

    # for each clientIP, a temp dictionary used to store the rtt along with the servername
    # key = averaged RTT to the repica server, value = replica server
    rttdic = {}
    # for each clientIP, a temp dictionary used to store the process, each process is to make a scamper call on one
    # replica instance. key = replica, value = the subprocess that being called
    processdic = {}

    for replica in replicas:
        # this is used to launch a new process to call one replica server to run active measurements against the client
        processdic[replica] = subprocess.Popen('ssh -i %s %s@%s "scamper -c "ping" -i %s |grep avg"'
              % (KEYFILE, USERNAME, replica, client_ip), stdout=subprocess.PIPE , shell=True)

    for replica in processdic:
        proc = processdic.get(replica)
        # actually running the ssh command here, and read out the results
        (out, err) = proc.communicate()
        try:
            # getting the average RTT
            avgRTT =  out.split('=')[1].split('/')[2]
        except:
            # If we can not get the RTT, something is wrong with this server, just u
            avgRTT = float('inf')
        rttdic[avgRTT] = replica
    # Update the CLIENT_ACTIVE_MEASUREMENTS_DICT, the value is the server with fastest ping result
    with LOCK_ACTIVE_DICT:
        mirtt = min(rttdic.keys())
        if mirtt == float('inf'):
            if client_ip in CLIENT_ACTIVE_MEASUREMENTS_DICT:
                del CLIENT_ACTIVE_MEASUREMENTS_DICT[client_ip]
        else:
            # print mirtt, rttdic
            CLIENT_ACTIVE_MEASUREMENTS_DICT[client_ip] = rttdic[mirtt]


# After updating all clients, sleep 30 seconds, do active measurement for every active client ip again
def ACTIVE_MEASUREMENT_UPDATE():
    while True:
        time.sleep(30)
        global ACTIVE_CLIENT_DICT
        global CLIENT_ACTIVE_MEASUREMENTS_DICT
        for client_ip in ACTIVE_CLIENT_DICT.keys():
            # spawn a thread to do active measure for this client
            # maybe we also want to sleep for one second between measuring each client
            time.sleep(1)
            t1 = threading.Thread(target=active_measure,args=(client_ip,))
            t1.daemon = True
            t1.start()

# This is used to get back the replica with best Active measurement result
def getCNameAndIPAddressActive(ip_addr):
    global CLIENT_ACTIVE_MEASUREMENTS_DICT
    global ACTIVE_CLIENT_DICT
    global DNS_RECORDS_DICT

    # This line has two jobs:
    # 1. if ip_addr has not seen before or already expired, put it in ACTIVE_CLIENT dictionary
    # 2. if ip_addr is in ACTIVE_CLIENT, update it's time clock in the expiring dictionary
    ACTIVE_CLIENT_DICT[ip_addr] = 0
    # if the client IP is already in the dictionary
    if ip_addr in CLIENT_ACTIVE_MEASUREMENTS_DICT:
        k = CLIENT_ACTIVE_MEASUREMENTS_DICT[ip_addr]
        v = DNS_RECORDS_DICT[k]
        return k,v
    return None, None

    
def geolocGetLocation(ip_addr):
    global CLIENT_GEOLOC_DICT
    global DNS_RECORDS_DICT
    # get location from ipinfo.io
    lat, lon = ipinfo.getLatLong(ip_addr)
    # get location from other sources eurekapi, then dbip, then
    try:
        if lat is None:
            lat, lon = eurek_dbip.getLatLong(ip_addr)    
    except:
        if not DEPLOYED:
            traceback.print_exc()
        return None, None
    # if no lat, long
    if lat is None:
        return None, None
    # calculate distance and get nearest host, GREAT CIRCLE distance
    closest_distance = float('inf')
    closest_host = ""
    client_loc = (lat, lon)
    for hst in DNS_RECORD_LOCATION_DICT:
        x = DNS_RECORD_LOCATION_DICT[hst]
        hst_loc = (x['lat'],x['lon'])
        hst_dist = geo_distance.great_circle(client_loc,hst_loc).miles   #heavy operation, compute intensive
        if hst_dist < closest_distance:
            closest_distance = hst_dist
            closest_host = hst
    # store that host in the cache with client IP, with a write lock
    with LOCK_GEOLOC_DICT:
        CLIENT_GEOLOC_DICT[ip_addr] = closest_host
    # return that host
    try:
        v = DNS_RECORDS_DICT[closest_host]
        return closest_host, v
    except:
        return None, None
    

def getCNameAndIPAddressGeoloc(ip_addr):
    global CLIENT_GEOLOC_DICT
    global DNS_RECORDS_DICT
    # try reading it from the cache.
    if ip_addr in CLIENT_GEOLOC_DICT:
        k = CLIENT_GEOLOC_DICT[ip_addr]
        v = DNS_RECORDS_DICT[k]
        return k, v
    # otherwise start a new thread and return nothing. for now. we'll see it next time
    t1 = threading.Thread(target=geolocGetLocation,args=(ip_addr,))
    t1.daemon = True
    t1.start()
    return None, None
    
def getCNameAndIPAddressDefault():
    global DNS_RECORDS_DICT
    k = DNS_RECORDS_DICT.keys()[0]
    v = DNS_RECORDS_DICT[k]
    return k, v


def signal_handler(signal, frame):
    print('Closing DNS server')
    sys.exit(0)


def getExternalIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("gmail.com", 80))
    x = (s.getsockname()[0])
    s.close()
    return x


class DNSUDPHandler(SocketServer.DatagramRequestHandler):
    def handle(self):
        global CDN_SPECIFIC_NAME
        dnsPacket = DNSPacket()
        if not DEPLOYED:
            print "Client: ", self.client_address
        dnsPacket.parsePacket(self.request[0].strip())
        client_ip = self.client_address[0]
        socket = self.request[1]
        try:
            question = dnsPacket.questions[0]
            questionName = question[0]
            if questionName == CDN_SPECIFIC_NAME:
                cname, ip = getCNameAndIPAddress(client_ip)
                dnsPacket.addAnswer(60, ip)
                if not DEPLOYED:
                    print "Replica: ",cname
            else:
                dnsPacket.rcode = 3  # Dave said: Drop requests to any other domain
            ##############################
        except:
            #traceback.print_exc()
            dnsPacket.question_count = 0
            dnsPacket.rcode = 2  #error
        responsePacket = dnsPacket.createResponse()
        socket.sendto(responsePacket, self.client_address)


def setGlobalVariables(args):
    global HOST
    global PORT
    global CDN_SPECIFIC_NAME
    global USERNAME
    global KEYFILE
    try:
        CDN_SPECIFIC_NAME = args[args.index('-n') + 1]
        PORT = args[args.index('-p') + 1]
        PORT = int(PORT)
        if PORT < 40000 or PORT > 0xFFFF:
            print "Use Port: 40000-65535"
            x = 1/0 # throw exception.
#        HOST = getExternalIP()
#        if DEPLOYED:
#            HOST = socket.gethostbyname(HOST)
#        else:
#            HOST = socket.gethostbyname(socket.gethostname())
        #HOST = socket.gethostbyname(socket.gethostname())
        #HOST = "0.0.0.0"
        HOST = ""
        working_dir = os.path.dirname(__file__)
        key_user_file = os.path.join(working_dir, 'key-user.txt')
        with open(key_user_file,'r') as f:
            line = f.readline()
            KEYFILE = line.split('***')[0]
            USERNAME = line.split('***')[1]

    except:
        print 'Usage: ./dnsserver -p <port> -n <name>'
        sys.exit()


def getHostnamesAndIPDict():
    global DEPLOYED
    global ORIGIN_SERVER
    if DEPLOYED:
        hostNamesFile = open("/course/cs5700sp16/ec2-hosts.txt", "r")
    else:
        hostNamesFile = open("ec2-hosts.txt", "r")
    hostNamesList = []
    for hostName in hostNamesFile:
        if hostName.startswith("ec2"):
            x = hostName.split("\t")[0]
            if x == ORIGIN_SERVER:
                continue
            hostNamesList.append(x)
    hostNameDict = {}
    for hostName in hostNamesList:
        hostNameDict[hostName] = socket.gethostbyname(hostName)
    return hostNameDict


def main(args):
    global PORT, CDN_SPECIFIC_NAME, HOST, DEPLOYED, DNS_RECORDS_DICT
    signal.signal(signal.SIGINT, signal_handler)
    # intialize things
    setGlobalVariables(args)
    #DNS_RECORDS_DICT = getHostnamesAndIPDict()
    # populate DNS records

    # start DNS Server
    server = SocketServer.ThreadingUDPServer((HOST, PORT), DNSUDPHandler)
    HOST, PORT = server.server_address
    if not DEPLOYED:
        print DNS_RECORDS_DICT
    print HOST + ":" + str(PORT)

    # spawn a thread to manage the active measurement dictionary
    amu = threading.Thread(target=ACTIVE_MEASUREMENT_UPDATE)
    amu.daemon = True
    amu.start()
    # handle requests
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv)
