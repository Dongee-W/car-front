from pyroutelib3 import Router # Import the router
from pyroutelib3_shortest import Router as r# Import the router

# tiachung_HSR	= 24.110421,120.613064
# tiachung_AP	= 24.269823, 120.608074
# tiachung_TRAIN= 24.136807,120.686931
# tiachung_LTR	= 24.139680,120.672764
# taichung_CH   = 24.163373,120.647872
# fongjia		= 24.178812,120.646648
# taichung_Art  = 24.252866,120.598712
router 			= r("cycle") # Initialise it


router 			= Router("cycle") # Initialise it
start 			= router.data.findNode(24.110421,120.613064) # Find start and end nodes
end 			= router.data.findNode(24.269823, 120.608074)
start_hour 		= 9
start_minute 	= 10
#num = 
status, route 	= router.doRoute(start, end, start_hour, start_minute, 10) # Find the route - a list of OSM nodes

if status == 'success':
    routeLatLons = list(map(router.nodeLatLon, route))

print ('transport:  cycle(speed = 8)'
+'\nstar_time:	9:10'
+'\narrive_time:  '+str(router.display()[0]['past_time']) 
+ '\ndistance:  '+str(router.display()[0]['distance'] )
+'\npm25exposure:  '+str(router.display()[0]['pm25exposure'])
+'\nlatlon: ' + str(routeLatLons ))

