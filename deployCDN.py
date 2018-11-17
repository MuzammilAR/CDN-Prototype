#! /usr/bin/env python
import sys, subprocess, os, threading

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
        if '-n' in args:
            name = args[args.index('-n')+1]
            args.remove('-n')
            args.remove(name)
        if '-u' in args:
            username = args[args.index('-u')+1]
            args.remove('-u')
            args.remove(username)
        if '-i' in args:
            keyfile = args[args.index('-i')+1]
            args.remove('-i')
            args.remove(keyfile)
        return port, origin, name , username, keyfile
    except:
        print 'Please provide the parameters as specified: -p <port> -o <origin> -n <name> -u <username> -i <keyfile>'
        sys.exit()
        
# please add -oStrictHostKeyChecking=no between scp and -r to auto add the server
def replicaThread(replica,port, oriServer, name, username, keyfile):
        subprocess.call('scp -r -i %s CDN %s@%s:'
              % (keyfile, username,replica), stdout=subprocess.PIPE , shell=True)
        subprocess.call('ssh -i %s %s@%s "make -C CDN/"'
              % (keyfile, username,replica), stdout=subprocess.PIPE , shell=True)


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

    # run following commands iteratively
    # scp the program's directory to remote server
    print 'Coping files to replica servers and making the executables'
    threadList = []
    for replica in replicas:
        t1 =threading.Thread(target=replicaThread, args=(replica,port, oriServer, name, username, keyfile))
        threadList.append(t1)
        t1.start()
    for curThread in threadList:
        curThread.join()

    print 'Coping files to DNS servers and make the executables'
    # It is important to write the keyfile and username into a file and then scp this file along with the key to DNS server
    # DNS server is going to use the keyfile and username to run scamper on replicas to get the active measurement
    keyfileName = keyfile.split('/')[-1]
    with open('key-user.txt','w') as f:
        f.writelines(keyfileName+'***'+username)

    # copy the CDN directory to DNS server
    subprocess.call('scp -r -i %s CDN %s@cs5700cdnproject.ccs.neu.edu'
              % (keyfile, username), stdout=subprocess.PIPE , shell=True)

    subprocess.call('scp -r -i %s key-user.txt %s@cs5700cdnproject.ccs.neu.edu:CDN/'
              % (keyfile, username), stdout=subprocess.PIPE , shell=True)

    subprocess.call('ssh -i %s %s@cs5700cdnproject.ccs.neu.edu "make -C CDN/"'
              % (keyfile, username), stdout=subprocess.PIPE , shell=True)

    # Copy the key to dns server
    subprocess.call('scp -r -i %s %s %s@cs5700cdnproject.ccs.neu.edu:CDN/'
              % (keyfile, keyfile, username), stdout=subprocess.PIPE , shell=True)

    subprocess.call('rm key-user.txt', stdout=subprocess.PIPE , shell=True)

    
if __name__=="__main__":
    main(sys.argv)