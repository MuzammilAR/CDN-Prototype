#! /usr/bin/env python
import sys,os,subprocess

def checkArgs(args):
    port = 0
    origin = ''
    name = ''
    username = ''
    keyfile = ''
    for arg in args:
        try:
            if '-p' in arg:
                port = arg.split('-p ')[1]
                port=int(port)
            if '-o' in arg:
                origin = arg.split('-o ')[1]
            if '-n' in arg:
                name = arg.split('-n ')[1]
            if '-u' in arg:
                username = arg.split('-u ')[1]
            if '-i' in arg:
                keyfile = arg.split('-i ')[1]
        except:
            print 'StopCDN Please provide the parameters as specified: -p <port\
> -o <origin> -n <name> -u <username> -i <keyfile>'
            sys.exit()
    return port, origin, name, username, keyfile


def main(argv):

    replicas = ['ec2-54-85-32-37.compute-1.amazonaws.com',
                'ec2-54-193-70-31.us-west-1.compute.amazonaws.com',
                'ec2-52-38-67-246.us-west-2.compute.amazonaws.com',
                'ec2-52-51-20-200.eu-west-1.compute.amazonaws.com',
                'ec2-52-29-65-165.eu-central-1.compute.amazonaws.com',
                'ec2-52-196-70-227.ap-northeast-1.compute.amazonaws.com',
                'ec2-54-169-117-213.ap-southeast-1.compute.amazonaws.com',
                'ec2-52-63-206-143.ap-southeast-2.compute.amazonaws.com',
                'ec2-54-233-185-94.sa-east-1.compute.amazonaws.com']

    # The server will be running on this port
    # and it will contact original server for content
    port, oriServer, name, username, keyfile= checkArgs(argv)
    print 'Killing the replica http servers and cleaning the cached files\n'
    for replica in replicas:

        subprocess.Popen('ssh -i %s %s@%s "fuser -k %s/tcp >/dev/null 2>&1 "' % (keyfile, username, replica, port),
                         stdout=subprocess.PIPE , shell=True)
        subprocess.Popen('ssh -i %s %s@%s "rm -r CDN/cache_* >/dev/null 2>&1 "' % (keyfile, username, replica),
                         stdout=subprocess.PIPE , shell=True)


    print 'Killing the dns server\n'
    # kill the dns server
    subprocess.Popen('ssh -i %s %s@cs5700cdnproject.ccs.neu.edu "fuser -k %s/udp"' % (keyfile, username, port),
                    stdout=subprocess.PIPE , shell=True)

if __name__=="__main__":
    main(sys.argv)
