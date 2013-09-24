import requests
import json
import csv
import time
import os

def open_global_csv(filename, labelList):
	"""Function to define global CSV writer objects."""
    csvfile=open(filename+'.csv', 'wb+')
    W=csv.writer(csvfile, delimiter=',', quotechar='"')
    #row headers below
    W.writerow(labelList)
    #writes header
    return W

#----START GLOBAL VARIABLES----

BIBCODE_LIST_FILENAME=raw_input('Bibcode list file name: ')
print("")#purely aesthetic spacing.

def ensure_dir(d):
	"""Makes sure a directory exists, and if it doesn't, it creates one."""
    if not os.path.exists(d):
        os.makedirs(d)
ensure_dir(BIBCODE_LIST_FILENAME)
BIB_PATH=os.path.abspath(BIBCODE_LIST_FILENAME)
ensure_dir(BIB_PATH+"/bibcodes")

ADS_URL_BASE='http://labs.adsabs.harvard.edu/adsabs/api/search/'
ADS_DEV_KEY=open('API_KEY.txt', 'r').read()
GEO_URL_BASE='http://maps.googleapis.com/maps/api/geocode/json'
ERROR_WRITER=open_global_csv(BIB_PATH+'/geoErrors', ['bibcode', 'loc', 'status','count','time'])
#^Opens csv to be used to record bibcodes and locations where the geocoordinates could not be found.
NOAFFIL_WRITER=open_global_csv(BIB_PATH+'/noAffil', ['bibcode'])
#^Opens csv to be used to record bibcodes with no affiliation data.
NOBIB_WRITER=open_global_csv(BIB_PATH+'/noBib', ['bibcode'])
#^Opens csv to be used to record bibcodes that the API could not find a record for.
SET_WRITER=open_global_csv(BIB_PATH+'/geo_affil_set', ['bibcode','Location','lat','long','address','country','state','trusted','count'])
#^Opens csv to be used to record all information for the current set of bibcodes.

#----END GLOBAL VARIABLES----

def adsQuery(bibcode):
	"""Takes a bibcode as an argument, returns a dictionary from the json that the ADS API returns."""
	time.sleep(1)
	apiBib='bibcode:'+bibcode
	Q={'dev_key':ADS_DEV_KEY, 'q':apiBib, 'fl':'aff'}
	adsRequest=requests.get(ADS_URL_BASE, params=Q)
	ADSreturndict=adsRequest.json()
	return ADSreturndict

def cleanLocation(loc):
	"""Cleaner for addresses, splits addresses with semicolons, takes the first affiliation. Also takes out any leading whitespace. clean_01 ensures utf-8 encoding, clean_02 splits clean_01 on ';'' if they're present, and makes clean_01 a list if they're not to normalize operations in both cases. clean_03 strips out leading whitespace from all items in clean_02. clean_04 removes empty strings from clean_03."""
	clean_01=loc.encode('utf-8')
	if ';' in clean_01:
		clean_02=clean_01.split(';')
	else:
		clean_02=[clean_01]
	clean_03=[i.lstrip() for i in clean_02]
	clean_04=filter(None,clean_03)
	return clean_04

def getAddrDict(bibcode):
	"""Makes a list of addresses from the affiliations of the ADS query for one bibcode, sends them to the cleaning function, then takes the set of unique affiliations and returns them as a dictionary, such that the affiliation is paired with the number of times it occured in that bibcode."""
	ads_dict=adsQuery(bibcode)
	cleanAddrList=[]
	addrDict={}
	try:
		addrList=ads_dict['results']['docs'][0]['aff']
		for i in addrList:
			loc=cleanLocation(i)
			for ele in loc:
				cleanAddrList.append(ele)
				uniqueAddrList=list(set(cleanAddrList))
				for i in uniqueAddrList:
					addrDict[i]=cleanAddrList.count(i)
		return addrDict
	except KeyError:
		print "Could not process {0}. Affiliations not recorded.".format(bibcode)
		writeList = [bibcode]
		NOAFFIL_WRITER.writerow(writeList)
		addrList=[]
		return 0
	except IndexError:
		print "Could not process {0}. The ADS API returned no results.".format(bibcode)
		writeList = [bibcode]
		NOBIB_WRITER.writerow(writeList)
		addrList=[]
		return 0

def open_output_csv(bibcode):
	"""Opens a csv file to write bibcode affiliation geocoding info to, returns a csv writer object."""
    csvfile=open('{0}/bibcodes/{1}.csv'.format(BIB_PATH,bibcode), 'wb+')
    W=csv.writer(csvfile, delimiter=',', quotechar='"')
    #row headers below
    W.writerow(['bibcode','Location','lat','long','address','country','state','trusted','count'])
    #writes header
    return W

def geoQuery(loc, bibcode, count):
	"""Takes a location and the bibcode and count from the address dictionary, and sends it to a Google API for geocoding. Responses are written into a list, to be written to later. Each column to be written to is assigned its own variable, and encoded in utf-8"""
	Q={'address':loc, 'sensor':'false'}
	try:
		geoRequest=requests.get(GEO_URL_BASE, params=Q)
		geoDict=geoRequest.json()
		if geoDict['status'] == 'OK':
			lat=geoDict['results'][0]['geometry']['location']['lat']
			lng=geoDict['results'][0]['geometry']['location']['lng']
			country='NULL'
			state='NULL'
			trusted=False
			for i in geoDict['results'][0]['address_components']:
				if 'country' in i['types']:
					country=i['long_name']
				if 'administrative_area_level_1' in i['types']:
					state=i['long_name']
				if 'route' in i['types']:
					trusted=True
			address=geoDict['results'][0]['formatted_address']
			lat=str(lat).encode('utf-8')
			lng=str(lng).encode('utf-8')
			country=country.encode('utf-8')
			state=state.encode('utf-8')
			address=address.encode('utf-8')
			count=str(count).encode('utf-8')
			bibcode=bibcode.encode('utf-8')
			writeList=[bibcode,loc,lat,lng,address,country,state,trusted,count]
		else:
			writeList=[bibcdoe, loc, geoDict['status'],count,time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())]
		return writeList
	except requests.exceptions.ConnectionError, e:
		print("Could not get geocoding information for {0}. Connection error:".format(bibcode))
		print(e)
		writeList=[bibcode, loc, "ConnectionError",count,time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())]
		return writeList

def geoQueryWriter(writeList, csvWriter):
	"""Takes writelist from previous function, as well as writer, determines whether query was successful based on writer length. Writes to either (error csv) or (set csv and bibcode csv)"""
	if len(writeList)>=6:
		csvWriter.writerow(writeList)
		SET_WRITER.writerow(writeList)
	elif len(writeList)==5:
		ERROR_WRITER.writerow(writeList)

def geoQueryContainer(bibcode):
	"""#container that runs the queries and writers, takes a bibcode to pass all the way down the chain of functions. Also reports status of script via print, makes script wait to reduce timeout errors from Google."""
	csvWriter=open_output_csv(bibcode)
	addrDict=getAddrDict(bibcode)
	try:
		addrLen=str(len(addrDict))
		print "Bibcode: {0} has {1} affiliation addresses to process.".format(bibcode, addrLen)
		for i in addrDict.keys():
			writeList=geoQuery(i,bibcode,addrDict[i])
			time.sleep(1)
			geoQueryWriter(writeList, csvWriter)
		return 0
	except TypeError:
		return 0

def openCSVreader(name):
	"""opens bibcode list, one row of a lot of bibcodes."""
	csvfile=open("{0}.csv".format(name), 'rb')
	R=csv.reader(csvfile, delimiter=',', quotechar='"')
	return R

def dedupeByAddress(csvname):
    R=openCSVreader(csvname)
    tempdict={}
    for row in R:
        if row[4]!="address":
            lat=row[2]
            lon=row[3]
            addr=row[4]
            country=row[5]
            state=row[6]
            count=int(row[8])
            if addr not in tempdict.keys():
                tempdict[addr]=[lat,lon,addr,state,country,count]
            else:
                tempdict[addr][5]+=count
	dedupedwriter=open_global_csv("{0}/geo_affil_set_deduped".format(BIB_PATH),["lat","long","address","state","country","count"])
    for key in tempdict.keys():
        dedupedwriter.writerow(tempdict[key])
    return 0

def geocodeBibcodeList(listname):
	"""Takes a csv with a list of bibcodes in one row, then tries to get the geocoding for all of them."""
	BibList=[row[0] for row in openCSVreader(listname)]
	LenBibList=len(BibList)
	counter=1
	for bibcode in BibList:
		geoQueryContainer(bibcode)
		strCounter=str(counter)
		strLenBibList=str(LenBibList)
		print "{0} of {1} bibcodes processed.".format(strCounter, strLenBibList)
		print ""
		counter+=1
	print("Finished geocoding. De-duplicating affiliations by address.")
	return 0

geocodeBibcodeList(BIBCODE_LIST_FILENAME)

dedupeByAddress("{0}/geo_affil_set".format(BIB_PATH))
print("")
print("Complete!")