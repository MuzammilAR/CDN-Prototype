# CDN Prototype

##### Note:
The httpserver and dnsserver executables can be found in the CDN folder after making.


## High Level Approach:
For the DNS server, we implement two schemes: Active measurements and IP Geolocation. 
In active measurements, in every 30 seconds, for all the live clients(seen in past 3 minutes), it will use scamper to ping them from all the replica servers and choose the closest server based on the average RTT. If this scheme fails, we look at the IP address of the client, use 3 different IP Geolocation sources (IPInfo, DBIP and EurekAPI) to find the latitude and the longitude of the client. These coordinates are used to calculate the distance(Great Circle distance in miles) between all the replicas and the client and the closest replica is returned on the next cache request. If both of these approaches fail, the we return the central European server, since it's geographically closest to all other continents.
For the HTTP server, we use both the memory and disk based caches. The memory based cache operates on the hotness(last seen) of the objects and tries to store all the objects that appear within a 1.5 minute interval.i.e each subsequent request for that same object appears within 1 minute of the previous one. The disk based cache works on simply removing the oldest object and replacing it with a new one. All, the incoming objects are added to the disk(if memory is not empty). If a disk object starts occuring more frequently, then we look at the number of times the object has been requested and compare it with the memory objects. This disk object replaces the memory objects with a lower count. So, we have a hot and a warm cache.
Our disk and memory cache's are hardcoded not to go above the recommended 10 MB.


## Design choices:
We designed a system to be as responsive as possible, therefore, our design of DNS server focuses on replying with an IP address of a replica server instead of waiting for the nearest IP during the first connection.
We assume that the DNS server is very close to the request client and any request to the server should be served as fast as possible.
For the HTTPServer, we needed two types of cache schemes, one for really hot(requested frequently) and one for warm objects.


## Perfomance Enhancement Techniques:
* Seperate threads with locks for caching and going for a very responsive server.
* Frequency(both time and count) based approach to save cache.


## Challenges:
* The main challenges that we faced was in development of the DNS server and creating a pointer in the answer section to the original question in the DNS packet. 
* The second main challenge was designing a system for the active measurements.

## Python Requirement:
* Mechanize
* GeoPy
* HTML
* Beautiful Soup 4
* expiringdict
