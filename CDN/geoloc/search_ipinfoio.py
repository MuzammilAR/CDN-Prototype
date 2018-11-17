import json
import urllib2 as urlopenner

#There's a 1000 query per day limit.
    
def parseJSON(obj):
    try:
        key="loc"
        if key in obj:
            loc = obj[key]
            x = loc.split(',')
            lat = float(x[0])
            lon = float(x[1])
            return lat, lon
        else:
            return None, None
    except:
        return None, None
    
def getLatLong(ip_address):
    search_address="http://ipinfo.io/"+ip_address+"/json"
    retrievedJSON=urlopenner.urlopen(search_address).read();
    pythonObject=json.loads(retrievedJSON)
    return parseJSON(pythonObject)
    
if __name__ == "__main__":
    getLatLong("1.1.1.1")
