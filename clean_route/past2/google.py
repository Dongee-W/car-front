import numpy as np
import pandas as pd

def googleRoute(start, end, mode="driving"):
    '''
    start/end format: "24.156944,120.665573"

    mode: driving, walking, bicycling, transit
    '''
    #query = f"https://maps.googleapis.com/maps/api/directions/json?origin=24.156944,120.665573&destination=24.169493,120.655157&key=AIzaSyC9L5sFNkXtsJ8IWGfwgbT-E6_T6jwf3iY"
    query = f"https://maps.googleapis.com/maps/api/directions/json?origin={start}&destination={end}&mode={mode}&key=AIzaSyC9L5sFNkXtsJ8IWGfwgbT-E6_T6jwf3iY"
    print(query)
    import requests
    import json
    r = requests.get(query)
    json = r.json()
    #print(json)
    distance = json["routes"][0]["legs"][0]["distance"]["value"]
    routeRaw = json["routes"][0]["legs"][0]["steps"]

    def extract_start(dict):
        return [dict["start_location"]["lat"], dict["start_location"]["lng"]]

    def extract_end(dict):
        return [dict["end_location"]["lat"], dict["end_location"]["lng"]]

    earlier = [extract_start(step) for step in routeRaw]
    later = extract_end(routeRaw[-1])

    earlier.append(later)
    return (distance, earlier)

def search_sensor(lat, lon):
    lonn=[119.3,120.0, 120.7 ,121.4, 122.1,122.8] #0.7
    latt=[25.1, 24.8, 24.5, 24.2, 23.9, 23.6, 23.3, 23.0, 22.7, 22.4, 22.1] #0.3
    column = 0
    raw = 0
    for i in range(5):
        if lonn[i] <=lon <lonn[i+1]:
            column = i+1
            break
    for j in range(10):
        if latt[j+1] <=lat <latt[j]:
            raw = j+1
            break
    return str((raw, column))

def interpolation(lon, lat, hour, minute):
    '''     preparing and resetting     ''' 
    # neighborNum = 10
    # sampled = self.interpolation_temporal_vector(hour, minute)
    sampled   = pd.read_csv('/Users/summerlight/Google Drive/oAC/project-mapping/clean_route/clean_route/past2/hello_herro.csv')

    nearest = []

    inverse = []
    total_distance_neighbor_inverse = 0
    weight = []
    tag = search_sensor(lat, lon)
    sampled = sampled[sampled["GRID"] == tag]

    distance = list(map(lambda x: eas_dist_sq(lat, lon, x[0], x[1]), list(zip(sampled["LATITUDE"], sampled["LONGTITUDE"]))))

    sampled["DIS"] = distance
    index = sampled["DIS"].idxmin()

    #for j in range(len(sampled)):
    #    dist_qr = self.eas_dist_sq(lat,lon, float(sampled['LATITUDE'][j]), float(sampled['LONGTITUDE'][j]))
    #    nearest.append([j, dist_qr])
    
    # nearest = sorted(nearest, key = lambda x: x[1])
    #min_station = min(nearest, key=lambda x:x[1])

    now, h = 'now', 'h'
    field_start = now+'+'+str(hour) +h
    if minute == 0:
        field_end = field_start
    else:
        field_end = now+'+'+str(hour+1) +h

    epsilon = float(1.0 * minute / 60.0)

    value = float(sampled[sampled.index == index][field_start]) * epsilon + float(sampled[sampled.index == index][field_end]) * (1-epsilon)
    # sampled[min_station[0]]
    # nearest[0:neighborNum]

    '''
    for i in range(len(nearest)):
        nearest[i].append(1/nearest[i][1])
        total_distance_neighbor_inverse = total_distance_neighbor_inverse + nearest[i][3]

    for i in nearest:
        weight.append([i[3]/total_distance_neighbor_inverse, i[2]])
        
    loc_val = sum([item[0] * item[1] for item in weight])
    '''
    return value

def pm25_exposure(array, transport):
    total_distance = 0
    total_exposure = 0
    for i in range(len(array) - 1):
        distance = eas_dist_sq(array[i+1][0], array[i+1][1], array[i][0], array[i][1])
        total_distance += distance
        time = duration(total_distance,transport)
        pm25 = interpolation(array[i+1][1], array[i+1][0], time[0], time[1])
        total_exposure += pm25 * distance
    return total_exposure


def duration(route_len, transport):
    if transport == "driving":
        velocity = 15 #in city , or 50
    elif transport == "bicycling":
        velocity = 8
    elif transport == "walking":
        velocity = 5
    elif transport == "transit":
        velocity = 12

    past_time = (route_len/velocity)*60

    return int(past_time / 60), past_time % 60

def eas_dist_sq(lat0,lon0, lat1, lon1):
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
    dist_sq = np.sqrt(a*a+b*b)
    return(dist_sq)