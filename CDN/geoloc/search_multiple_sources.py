import mechanize

# Python 2.7
# Author: Muzammil Abdul Rehman
# This function takes an IP address, searches multiple directory sources and return the html.
# These sources are taken from https://www.iplocation.net/
#Source: IP2Location
#Source: EurekAPI
#Source: DB-IP
#Source: ipinfo.io
#Source: GeoLiteCity

def serch_multiple_sources(ip_address):
    URL="https://www.iplocation.net/"
    br = mechanize.Browser()
    br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    br.set_handle_robots(False)
    br.open(URL)
    br.form =  list(br.forms())[0]
    br.form["query"] = ip_address
    r=br.submit()
    return r.read()
    
if __name__ == '__main__':
    serch_multiple_sources("1.1.1.1")
