from django.shortcuts import render
from django.http import JsonResponse
from django.http import HttpResponse

from urllib.request import urlopen

import json
from . import past2

def planCleanRoute(request):
    context = {}
    return render(request, 'planner.html', context)

def feedback(request):
    context = {}
    return render(request, 'feedback.html', context)

def ajaxCall(request):
    starting = request.GET.get('starting', None)
    destination = request.GET.get('destination', None)
    mode = request.GET.get('mode', None)

    lat_start = float(starting.split(",")[0])
    lon_start = float(starting.split(",")[1])

    lat_destination = float(destination.split(",")[0])
    lon_destination = float(destination.split(",")[1])

    data = urlopen(f'http://localhost:8080/car?latFrom={lat_start}&lonFrom={lon_start}&latTo={lat_destination}&lonTo={lon_destination}&mode=driving').read()
    print(data)
    return JsonResponse(json.loads(data))


def oldAjaxCall(request):
    starting = request.GET.get('starting', None)
    destination = request.GET.get('destination', None)
    mode = request.GET.get('mode', None)

    mapping = {"car": "driving", "foot": "walking", "cycle": "driving", "scooter": "driving"}
    mode_to_icon = {"car": "car", "foot": "male", "cycle": "bicycle", "scooter": "motorcycle"}

    lat_start = float(starting.split(",")[0])
    lon_start = float(starting.split(",")[1])

    lat_destination = float(destination.split(",")[0])
    lon_destination = float(destination.split(",")[1])

    router 			= past2.Router(mode) # Initialise it
    start 			= router.data.findNode(lat_start,lon_start) # Find start and end nodes
    end 			= router.data.findNode(lat_destination, lon_destination)
    #start 			= router.data.findNode(25.042574,121.614649)
    #end 			= router.data.findNode(25.055222,121.617254)
    start_hour 		= 0
    start_minute 	= 0
    numNeighbor = 1
    status, route 	= router.doRoute(start, end, start_hour, start_minute, numNeighbor)

    if status == 'success':
        pm25_CAR = "{:.1f}".format(router.display()[0]['pm25exposure'])
        distance_CAR = "{:.3f}".format(router.display()[0]['distance'])
        CAR_route = list(map(router.nodeLatLon, route))
        google_route = past2.google.googleRoute(starting, destination, mapping[mode])
        gp = "{:.1f}".format(past2.google.pm25_exposure(google_route[1], mapping[mode]))

        CAR_TIME = router.display()[0]['past_time']
        CAR_hour = CAR_TIME.split(":")[0]
        CAR_minute = CAR_TIME.split(":")[1]
        if CAR_hour == '0':
            CAR_time_string = CAR_minute + "min"
        else:
            CAR_time_string = CAR_hour + "h " + CAR_minute + "min"

        google_distance = float(google_route[0])/1000
        google_time = past2.google.duration(google_distance, mapping[mode])

        if google_time[0] == 0:
            google_time_string = str(int(google_time[1])) + "min"
        else:
            google_time_string = str(google_time[0]) + "h " + str(int(google_time[1])) + "min"

        response = {"CAR": CAR_route, "google": google_route[1], "CAR_DISTANCE": distance_CAR, 
        "CAR_PM25": pm25_CAR, "GOOGLE_DISTANCE": google_distance, "GOOGLE_PM25": gp, 
        "ICON": mode_to_icon[mode], "CAR_TIME": CAR_time_string, "GOOGLE_TIME": google_time_string}
    '''
    data = {"path" : [[24.1404778, 120.6833498], [24.1397717, 120.6827008], [24.1401824, 120.6822425], [24.1408426, 120.6814666], [24.1415242, 120.6806703], [24.1418009, 120.6803474], [24.1421395, 120.6799555], [24.1424851, 120.6795297], [24.1428656, 120.6791293], [24.1433512, 120.6786057], [24.1435476, 120.6783504], [24.143875, 120.6779563], [24.1441446, 120.6776162], [24.1445915, 120.6771818], [24.1450672, 120.6766406], [24.1455122, 120.6761], [24.1459277, 120.6755966], [24.146321, 120.6751337], [24.1465242, 120.674902], [24.1467834, 120.6745967], [24.1472303, 120.6740523], [24.1474537, 120.6738047], [24.1476983, 120.6735459], [24.1477444, 120.6734922], [24.1478585, 120.6733641], [24.1484086, 120.6727214], [24.149108, 120.6719231]]}'''
    return JsonResponse(response)
