#!/usr/bin/env python3
#--------------------------------1117--------------------------------------------
#pm2.5
import os
import re
import sys
import math
import osmapi
import xml.etree.ElementTree as etree
from . import (tiledata, tilenames)
import pandas as pd
import numpy as np

TYPES = {
    "car": {
        "weights": {"motorway": 10, "trunk": 10, "primary": 2, "secondary": 1.5, "tertiary": 1, "unclassified": 1, "residential": 0.7, "track": 0.5, "service": 0.5},
        "access": ["access", "vehicle", "motor_vehicle", "motorcar"]},
    "scooter": {
        "weights": {"primary": 2, "secondary": 1.5, "tertiary": 1, "unclassified": 1, "residential": 2, "track": 1, "service": 1},
        "access": ["access", "vehicle", "bicycle", "vehicle", "motor_vehicle", "motorcar"]},
    "cycle": {
        "weights": {"primary": 0.3, "secondary": 0.9, "tertiary": 1, "unclassified": 1, "cycleway": 2, "residential": 2.5, "track": 1, "service": 1, "bridleway": 0.8, "footway": 0.8, "steps": 0.5, "path": 1},
            "access": ["access", "vehicle", "bicycle"]},
    "foot": {
        "weights": {"trunk": 0.3, "primary": 0.6, "secondary": 0.95, "tertiary": 1, "unclassified": 1, "residential": 1, "track": 1, "service": 1, "bridleway": 1, "footway": 1.2, "path": 1.2, "steps": 1.15},
        "access": ["access", "vehicle", "motor_vehicle", "motorcar"]},
}

# motorway是國道 , trunk是快速道路 , primary 省道 ,secondary 縣/市道 , tertiary 鄉/區道, service支路, steps階
# 縣道、鄉道、省道都可以騎單車。
# 高速公路和快速道路、鐵路和高速鐵路是不可以騎單車的。
# 機車不能上快速道路，但省道 縣道都可以騎
class Datastore(object):
    """Parse an OSM file looking for routing information"""
    def __init__(self, transport, localfile=""):
        """Initialise an OSM-file parser"""
        self.routing = {}
        self.rnodes = {}
        self.tiles = []
        self.transport = transport
        self.localFile = localfile
        self.type = TYPES[transport]

        if self.localFile:
            self.loadOsm(self.localFile)
            self.api = None

        else:
            self.api = osmapi.OsmApi(api="api.openstreetmap.org")

    def getArea(self, lat, lon):
        """Download data in the vicinity of a lat/long.
        Return filename to existing or newly downloaded .osm file."""

        z = tiledata.DownloadLevel()
        (x,y) = tilenames.tileXY(lat, lon, z)

        tileID = '%d,%d'%(x,y)
        if self.localFile or tileID in self.tiles:
            return

        self.tiles.append(tileID)

        filename = tiledata.GetOsmTileData(z,x,y)
        #print "Loading %d,%d at z%d from %s" % (x,y,z,filename)
        return(self.loadOsm(filename))

    def _allowedVehicle(self, tags):
        "Check way against access tags"

        # Default to true
        allowed = True

        # Priority is ascending in the access array
        for key in self.type["access"]:
            if key in tags:
                if tags[key] in ("no", "private"): allowed = False
                else: allowed =  True

        return(allowed)

    def getElementAttributes(self, element):
        result = {}
        for k, v in element.attrib.items():
            if k == "uid": v = int(v)
            elif k == "changeset": v = int(v)
            elif k == "version": v = int(v)
            elif k == "id": v = int(v)
            elif k == "lat": v = float(v)
            elif k == "lon": v = float(v)
            elif k == "open": v = (v == "true")
            elif k == "visible": v = (v == "true")
            elif k == "ref": v = int(v)
            elif k == "comments_count": v = int(v)
            result[k] = v
        return result

    def getElementTags(self, element):
        result = {}
        for child in element:
            if child.tag =="tag":
                k = child.attrib["k"]
                v = child.attrib["v"]
                result[k] = v
        return result

    def parseOsmFile(self, filename):
        result = []
        with open(filename, "r", encoding="utf-8") as f:
            for event, elem in etree.iterparse(f): # events=['end']
                if elem.tag == "node":
                    data = self.getElementAttributes(elem)
                    data["tag"] = self.getElementTags(elem)
                    result.append({
                        "type": "node",
                        "data": data
                    })
                elif elem.tag == "way":
                    data = self.getElementAttributes(elem)
                    data["tag"] = self.getElementTags(elem)
                    data["nd"] = []
                    for child in elem:
                        if child.tag == "nd": data["nd"].append(int(child.attrib["ref"]))
                    result.append({
                        "type": "way",
                        "data": data
                    })
                elif elem.tag == "relation":
                    data = self.getElementAttributes(elem)
                    data["tag"] = self.getElementTags(elem)
                    data["member"] = []
                    for child in elem:
                        if child.tag == " member": data["member"].append(self.getElementAttributes(child))
                    result.append({
                        "type": "relation",
                        "data": data
                    })
                    elem.clear()
        return result

    def loadOsm(self, filename):
        if(not os.path.exists(filename)):
            print("No such data file %s" % filename)
            return(False)

        nodes, ways = {}, {}

        data = self.parseOsmFile(filename)
        # data = [{ type: node|way|relation, data: {}},...]

        for x in data:
            try:
                if x['type'] == 'node':
                    nodes[x['data']['id']] = x['data']
                elif x['type'] == 'way':
                    ways[x['data']['id']] = x['data']
                else:
                    continue
            except KeyError:
                # Don't care about bad data (no type/data key)
                continue

        for way_id, way_data in ways.items():
            way_nodes = []
            for nd in way_data['nd']:
                if nd not in nodes: continue
                way_nodes.append([nodes[nd]['id'], nodes[nd]['lat'], nodes[nd]['lon']])
            self.storeWay(way_id, way_data['tag'], way_nodes)

        return(True)

    def storeWay(self, wayID, tags, nodes):
        highway = self.equivalent(tags.get("highway", ""))
        railway = self.equivalent(tags.get("railway", ""))
        oneway = tags.get("oneway", "")

        # Oneway is default on roundabouts
        if not oneway and tags.get("junction", "") in ["roundabout", "circular"]:
            oneway = "true"

        # Calculate what vehicles can use this route
        weight = self.type["weights"].get(highway, 0) or \
                 self.type["weights"].get(railway, 0)

        # Check against access tags
        if not self._allowedVehicle(tags): weight = 0

        # Store routing information
        last = [None, None, None]

        for node in nodes:
            (node_id, x, y) = node
            if last[0]:
                if weight != 0:
                    if oneway not in ["-1"]:
                        self.addLink(last[0], node_id, weight)
                        self.makeNodeRouteable(last)
                    if oneway not in ["yes", "true", "1"] or self.transport == "foot":
                        self.addLink(node_id, last[0], weight)
                        self.makeNodeRouteable(node)
            last = node

    def makeNodeRouteable(self, node):
        self.rnodes[node[0]] = [node[1],node[2]]

    def addLink(self, fr, to, weight=1):
        """Add a routeable edge to the scenario"""
        if fr not in self.routing:
            self.routing[fr] = {}
        self.routing[fr][to] = weight

    def equivalent(self, tag):
        """Simplifies a bunch of tags to nearly-equivalent ones"""
        equivalent = { \
            "motorway_link": "motorway",
            "trunk_link": "trunk",
            "primary_link": "primary",
            "secondary_link": "secondary",
            "tertiary_link": "tertiary",
            "minor": "unclassified",
            "pedestrian": "footway",
            "platform": "footway",
        }
        try: return(equivalent[tag])
        except KeyError: return(tag)

    def findNode(self, lat, lon):
        """Find the nearest node that can be the start of a route"""
        self.getArea(lat,lon)
        maxDist = 1E+20
        nodeFound = None
        posFound = None
        for (node_id,pos) in list(self.rnodes.items()):

            EARTH_R = 6372.8
            lat0 = np.radians(pos[0])
            lon0 = np.radians(pos[1])
            lat1    = np.radians(lat)
            lon1    = np.radians(lon)
            dlon = lon0 - lon1
            y = np.sqrt(
                (np.cos(lat1) * np.sin(dlon)) ** 2
                 + (np.cos(lat0) * np.sin(lat1) 
                 - np.sin(lat0) * np.cos(lat1) * np.cos(dlon)) ** 2)
            x = np.sin(lat0) * np.sin(lat1) + \
                np.cos(lat0) * np.cos(lat1) * np.cos(dlon)
            c = np.arctan2(y, x)
            dist = EARTH_R * c
            dist = (dist)**2

            if(dist < maxDist):
                maxDist = dist
                nodeFound = node_id
                posFound = pos
        # print("found at %s"%str(posFound))
        return(nodeFound)

    def report(self):
        """Display some info about the loaded data"""
        print("Loaded %d nodes" % len(list(self.rnodes.keys())))
        print("Loaded %d %s routes" % (len(list(self.routing.keys())), self.transport))

class Router(object):
    def __init__(self, transport, localfile=""):
        self.data = Datastore(transport, localfile)

    def distance(self, n1, n2):
        lat0 = np.radians(self.data.rnodes[n1][0])
        lon0 = np.radians(self.data.rnodes[n1][1])
        lat1 = np.radians(self.data.rnodes[n2][0])
        lon1 = np.radians(self.data.rnodes[n2][1])
        # """Return the distance (in km) between two points in geographical coordinates."""
        lat_dis = 111.2 #111.22634257109472 =370.35302229119566/(25.263236-21.933512)

        if lon0 < 22.7:
            lon_dis = 102.9 #102.90127045510803 = 202.4798588872203/(122.023366-120.055656) at 22.3077285
        elif 22.7<=lon0< 23.4:
            lon_dis= 102.3 #102.34096828979374=201.3773467135097/(122.023366-120.055656) at 23.0561615
        else:
            lon_dis= 101.8 #101.76320306104364= 200.24047229524584/(122.023366-120.055656) at 23.8045945

        a = (lon0 - lon1)*lon_dis
        b = (lat1-lat0) *lat_dis
        dist_sq = a*a+b*b
        return(dist_sq)

    def eas_dist_sq(self,lat0,lon0, lat1, lon1):
        # """Return the distance (in km) between two points in geographical coordinates."""
        lat_dis = 111.2 #111.22634257109472 =370.35302229119566/(25.263236-21.933512)

        if lon0 < 22.7:
            lon_dis = 102.9 #102.90127045510803 = 202.4798588872203/(122.023366-120.055656) at 22.3077285
        elif 22.7<=lon0< 23.4:
            lon_dis= 102.3 #102.34096828979374=201.3773467135097/(122.023366-120.055656) at 23.0561615
        else:
            lon_dis= 101.8 #101.76320306104364= 200.24047229524584/(122.023366-120.055656) at 23.8045945
            a = (lon0 - lon1)*lon_dis
            b = (lat1-lat0) *lat_dis
            dist_sq = a*a+b*b
        return(dist_sq)

    def distance2(self, n1, n2):
        """Return the distance (in km) between two points in 
        geographical coordinates."""
        EARTH_R = 6372.8 #6372.7982
        lat0 = np.radians(self.data.rnodes[n1][0])
        lon0 = np.radians(self.data.rnodes[n1][1])
        lat1 = np.radians(self.data.rnodes[n2][0])
        lon1 = np.radians(self.data.rnodes[n2][1])
        dlon = lon0 - lon1
        y = np.sqrt(
            (np.cos(lat1) * np.sin(dlon)) ** 2
             + (np.cos(lat0) * np.sin(lat1) 
             - np.sin(lat0) * np.cos(lat1) * np.cos(dlon)) ** 2)
        x = np.sin(lat0) * np.sin(lat1) + \
            np.cos(lat0) * np.cos(lat1) * np.cos(dlon)
        c = np.arctan2(y, x)
        dist = EARTH_R * c
        return(dist)

    def nodeLatLon(self, node):
        """Get node's lat lon"""
        lat, lon = self.data.rnodes[node][0], self.data.rnodes[node][1]
        return([lat, lon])

    def doRoute(self, start, end, start_hour, start_minute, neighborNum):
        """Do the routing"""
        self.searchEnd = end
        closed         = [start]
        self.queue     = []

        self.start_hour = start_hour
        self.start_minute = start_minute

        self.neighborNum = neighborNum

        # Start by queueing all outbound links from the start node
        blankQueueItem = {'end':-1,'distance':0,'nodes':str(start),'pm25exposure':0}
        pathid = 0
        try:
            for i, weight in self.data.routing[start].items():
                self._addToQueue(start,i, blankQueueItem, pathid, weight)
        except KeyError:
            return('no_such_node',[])

        # Limit for how long it will search
        count = 0
        
        while count < 1000000:
            count = count + 1
            try:
                nextItem = self.queue.pop(0)
            except IndexError:
                # Queue is empty: failed
                # TODO: return partial route?
                return('no_route',[])
            x = nextItem['end']
            if x in closed: continue
            if x == end:
                # Found the end node - success
                self.queue.insert(0,nextItem)
                routeNodes = [int(i) for i in nextItem['nodes'].split(",")]
                return('success', routeNodes)
            closed.append(x)
            try:
                for i, weight in self.data.routing[x].items():
                    pathid += 1
                    if not i in closed:
                        self._addToQueue(x,i,nextItem, pathid, weight)
            except KeyError:
                pass
        else:
            return('gave_up',[])

    def _addToQueue(self, start, end, queueSoFar, pathid, weight=1):
        """Add another potential route to the queue"""        
        end_pos = self.data.rnodes[end]
        self.data.getArea(end_pos[0], end_pos[1])# getArea() checks that map data is available around the end-point,
                                                 # and downloads it if necessary
        # TODO: we could reduce downloads even more by only getting data around the tip of the route, rather than around all nodes linked from the tip
        
        start_hour      = self.start_hour
        start_minute    = self.start_minute
        neighborNum     = self.neighborNum

        # If already in queue, ignore
        for test in self.queue:
            if test['end'] == end: return
        distance = self.distance(start, end)
        if(weight == 0): return
        distance = distance #/ weight

        # Create a hash for all the route's attributes
        distanceSoFar = queueSoFar['distance']
        exposureSoFar = queueSoFar['pm25exposure']
        past_time     = self.duration(start_hour, start_minute, (distanceSoFar+distance))

        queueItem = { \
            'pathid'        :pathid,
            'past_time'     :str(past_time[0]) +":"+ str(past_time[1]),
            'distance'      :distanceSoFar + distance,
            'pm25exposure'  :exposureSoFar + distance * self.interpolation_spatial_vector(self.data.rnodes[start][1],  self.data.rnodes[start][0], past_time[0], past_time[1]),
            'maxexposure'   :exposureSoFar + self.distance(end, self.searchEnd) * self.interpolation_spatial_vector(self.data.rnodes[start][1], self.data.rnodes[start][0], past_time[0], past_time[1]),
            'maxdistance'   :distanceSoFar + self.distance(end, self.searchEnd),
            'nodes'         :queueSoFar['nodes'] + "," + str(end),
            'end'           :end
        }

        # Try to insert, keeping the queue ordered by decreasing worst-case distance
        count = 0
        for test in self.queue:
            if test['maxexposure'] > queueItem['maxexposure']:
                self.queue.insert(count,queueItem)
                break
            count = count + 1
        else:
            self.queue.append(queueItem)

    def display(self):
        return (self.queue)

    def interpolation_temporal_vector(self, hour, minute):
        #hour:minute is between 8am and 12pm
        '''     preparing and resetting     ''' 
        sampled   = pd.read_csv('/Users/summerlight/Google Drive/oAC/project-mapping/main_code/past2/res_id.CSV')
        epsilon = float(1.0 * minute / 60.0)
        X, am, pm      = 'X', 'am', 'pm'
        field_start = X+str(hour)  +am
        if minute == 0:
            field_end = field_start
        else:
            field_end = X+str(hour+1)+am

        newTimeValue = []
        for i in range(len(sampled[field_start])):
            newTimeValue.extend([sampled[field_start][i]*   epsilon+\
                                      sampled[field_end][i]  *(1-epsilon)])
        sampled['pm2.5'] = newTimeValue
        return sampled

    def interpolation_spatial_vector(self, lon, lat, hour, minute):
        '''     preparing and resetting     ''' 
        # neighborNum = 10
        sampled = self.interpolation_temporal_vector(hour, minute)
        nearest = []
        neighborNum = self.neighborNum
        inverse = []
        total_distance_neighbor_inverse = 0
        weight = []
        
        for j in range(len(sampled)):
            dist_qr = self.eas_dist_sq(lat,lon, float(sampled['lat'][j]), float(sampled['lon'][j]))
            nearest.append([j, dist_qr, sampled['pm2.5'][j]])
                

        nearest = sorted(nearest, key = lambda x: x[1])
        nearest = nearest[0:neighborNum]

        for i in range(len(nearest)):
            nearest[i].append(1/nearest[i][1])
            total_distance_neighbor_inverse = total_distance_neighbor_inverse + nearest[i][3]

        for i in nearest:
            weight.append([i[3]/total_distance_neighbor_inverse, i[2]])
            
        loc_val = sum([item[0] * item[1] for item in weight])
        return loc_val


    def duration(self, start_hour, start_minute, route_len):
        if   self.data.transport == "car":
            velocity = 15 #in city , or 50
        elif self.data.transport == "cycle":
            velocity = 8
        elif self.data.transport == "foot":
            velocity = 5
        elif self.data.transport == "scooter":
            velocity = 15


        past_time = (route_len/velocity)*60+start_minute
        
        if (past_time >= 60 and past_time<120): # minute
            next_hour   = start_hour+1
            next_minute = past_time - 60
        elif past_time>=120:
            next_hour   = start_hour+2
            next_minute = past_time - 120            
        else:
            next_hour   = start_hour
            next_minute = past_time
        return next_hour, next_minute
        
