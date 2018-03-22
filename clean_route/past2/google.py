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
    print(json)
    routeRaw = json["routes"][0]["legs"][0]["steps"]

    def extract_start(dict):
        return [dict["start_location"]["lat"], dict["start_location"]["lng"]]

    def extract_end(dict):
        return [dict["end_location"]["lat"], dict["end_location"]["lng"]]

    earlier = [extract_start(step) for step in routeRaw]
    later = extract_end(routeRaw[-1])

    earlier.append(later)
    return earlier