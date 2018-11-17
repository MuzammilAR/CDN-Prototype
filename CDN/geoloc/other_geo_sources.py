from bs4 import BeautifulSoup
import search_multiple_sources as SMS
import traceback

def getAllSrcLocation(data):
    try:
        latitude=float(data[6])
        longitude=float(data[7])
        if latitude == 0:
            x =1/0
    except:
        latitude = None
        longitude = None
    return latitude, longitude

    
# todo. insert to database, return a dict with all the country
#names and sources for classifier!
def insertDataSetToDatabase(dataSet):
    loc_sc_dict = {}
    # ip2location
    data = dataSet[0][1]
    temp = dataSet[0][3]
    for ele in temp:
        data.append(ele)
    lat, lon = getAllSrcLocation(data)
    if lat is not None:
        return lat, lon
    #ipinfo
    data = dataSet[1][1]
    temp = dataSet[1][3]
    for ele in temp:
        data.append(ele)
    lat, lon = getAllSrcLocation(data)
    if lat is not None:
        return lat, lon
    #eurekapi
    data = dataSet[2][1]
    temp = dataSet[2][3]
    for ele in temp:
        data.append(ele)
    lat, lon = getAllSrcLocation(data)
    if lat is not None:
        return lat, lon
    #dbip
    data = dataSet[3][1]
    temp = dataSet[3][3]
    lat, lon = getAllSrcLocation(data)
    if lat is not None:
        return lat, lon
    #maxmind
    if len(dataSet) < 5:
        loc_sc_dict['maxmind_country'] = ''
        return loc_sc_dict
    data = dataSet[4][1]
    temp = dataSet[4][3]
    for ele in temp:
        data.append(ele)
    lat, lon = getAllSrcLocation(data)
    if lat is not None:
        return lat, lon
        
    return None, None


def parseHTML(returnedHTML):
    soup = BeautifulSoup(returnedHTML, 'html.parser')
    tables = soup.findAll('table')
    dataSet = []
    for table in tables:
        data = []
        rows = table.findAll('tr')
        for row in rows:
            cols = row.findAll('td')
            cols = [elem.text.strip() for elem in cols]
            data.append([ele for ele in cols])  # Get rid of empty values
        dataSet.append(data)
    return insertDataSetToDatabase(dataSet)

def getLatLong(ip_address):
    returnedHTML = SMS.serch_multiple_sources(ip_address)
    return parseHTML(returnedHTML)

if __name__ == "__main__":
    getLatLong("1.1.1.1")
