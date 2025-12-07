import time
import random
import requests
import folium

# ---------------------------------------
# USER INPUTS
# ---------------------------------------
country_name = input("Enter the COUNTRY name: ").strip()

location_names = [
    "Marina Bay Sands",
    "Changi Airport",
    "VivoCity",
    "Chancellor @ Orchard Singapore",
    "Value hotel thomson",
    "Singapore Zoo",
    "Sentosa"
]

print("\nAvailable locations:")
for loc in location_names:
    print(" -", loc)

start_location_name = input("\nEnter your START location: ").strip()
end_location_name = input("Enter your END location (can be SAME as start): ").strip()

if start_location_name not in location_names:
    raise ValueError("Invalid START location.")
if end_location_name not in location_names:
    raise ValueError("Invalid END location.")

round_trip = start_location_name == end_location_name
if round_trip:
    print("\nRound Trip Mode activated (start and end are same).")
else:
    print("\nOne-way route from start to end.")

print(f"\nStart = {start_location_name}")
print(f"End   = {end_location_name}\n")

# ---------------------------------------
# CONSTANTS
# ---------------------------------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "route-optimizer (vsrajan2k@gmail.com)"
GEOCODE_SLEEP = 1.0

OSRM_URL_BASE = "http://router.project-osrm.org/route/v1/driving"

POP_SIZE = 60
GENERATIONS = 200
MUTATION_RATE = 0.03
SELECT_SAMPLE = 5

OUTPUT_HTML = "optimized_route.html"

# ---------------------------------------
# GEOCODE FUNCTION
# ---------------------------------------
def geocode_inside_country(place, country):
    params = {
        "q": place,
        "format": "json",
        "addressdetails": 1,
        "limit": 5
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        results = r.json()
        for item in results:
            if "address" in item and item["address"].get("country"):
                found_country = item["address"]["country"]
                if found_country.lower() == country.lower():
                    return float(item["lat"]), float(item["lon"])
        return None
    except Exception as e:
        print(f"Geocode error for '{place}': {e}")
        return None

# ---------------------------------------
# GEOCODE ALL LOCATIONS
# ---------------------------------------
print("\nGeocoding locations in:", country_name)
locations = {}
for place in location_names:
    coord = geocode_inside_country(place, country_name)
    if coord:
        locations[place] = coord
        print(f"  ✓ {place} -> {coord}")
    else:
        print(f"  ❌ {place} not found.")
    time.sleep(GEOCODE_SLEEP)

if len(locations) < 2:
    raise SystemExit("Not enough locations.")

city_list = list(locations.items())  # (name, (lat,lon))
N = len(city_list)

start_index = next(i for i, (name, _) in enumerate(city_list) if name == start_location_name)
end_index = next(i for i, (name, _) in enumerate(city_list) if name == end_location_name)

# ---------------------------------------
# OSRM DISTANCE
# ---------------------------------------
def osrm_distance(c1, c2):
    lat1, lon1 = c1
    lat2, lon2 = c2
    url = f"{OSRM_URL_BASE}/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()["routes"][0]["distance"] / 1000
    except:
        return 999999

print("\nBuilding distance matrix...")
distance_matrix = [[0] * N for _ in range(N)]
for i in range(N):
    for j in range(N):
        if i != j:
            distance_matrix[i][j] = osrm_distance(city_list[i][1], city_list[j][1])
print("Distance matrix ready.\n")

# ---------------------------------------
# ROUTE DISTANCE
# ---------------------------------------
def route_distance(route):
    total = 0
    for i in range(len(route) - 1):
        total += distance_matrix[route[i]][route[i + 1]]
    return total

# ---------------------------------------
# GENETIC ALGORITHM (safe crossover)
# ---------------------------------------
def create_route():
    route = list(range(N))
    route.remove(start_index)
    if not round_trip:
        route.remove(end_index)
    random.shuffle(route)
    if round_trip:
        return [start_index] + route + [start_index]
    else:
        return [start_index] + route + [end_index]

def select(pop):
    sample = random.sample(pop, SELECT_SAMPLE)
    return min(sample, key=route_distance)

def crossover(p1, p2):
    child = [None] * N
    child[0] = start_index
    child[-1] = start_index if round_trip else end_index

    mid1 = p1[1:-1]
    mid2 = p2[1:-1]

    # Safe slice copy
    slice_len = min(len(mid1), N-2)
    start, end = sorted(random.sample(range(1, N-1), 2))
    end = min(end, start + slice_len)
    child[start:end] = mid1[:end-start]

    # Fill remaining None with mid2
    fill = [x for x in mid2 if x not in child]
    for i in range(1, N-1):
        if child[i] is None and fill:
            child[i] = fill.pop(0)
    return child

def mutate(route):
    lock_last = 0 if round_trip else 1
    for i in range(1, N - lock_last):
        if random.random() < MUTATION_RATE:
            j = random.randint(1, N - lock_last - 1)
            route[i], route[j] = route[j], route[i]
    return route

def run_ga():
    pop = [create_route() for _ in range(POP_SIZE)]
    best = min(pop, key=route_distance)
    for _ in range(GENERATIONS):
        new_pop = []
        for _ in range(POP_SIZE):
            c = crossover(select(pop), select(pop))
            mutate(c)
            new_pop.append(c)
        pop = new_pop
        cb = min(pop, key=route_distance)
        if route_distance(cb) < route_distance(best):
            best = cb
    return best

# ---------------------------------------
# RUN OPTIMIZER
# ---------------------------------------
print("Optimizing route...\n")
best_route = run_ga()

print("Optimized Route:")
for idx in best_route:
    print(" -", city_list[idx][0])
print("\nTotal Distance:", route_distance(best_route), "km")

# ---------------------------------------
# DRAW MAP
# ---------------------------------------
avg_lat = sum(lat for _, (lat, lon) in city_list) / N
avg_lon = sum(lon for _, (lat, lon) in city_list) / N

route_map = folium.Map(location=(avg_lat, avg_lon), zoom_start=12)
coords = []

for n, idx in enumerate(best_route):
    name, (lat, lon) = city_list[idx]
    if idx == start_index and n == 0:
        color = "green"
        popup = f"START → {name}"
    elif idx == (start_index if round_trip else end_index) and n == len(best_route)-1:
        color = "red"
        popup = f"END → {name}"
    else:
        color = "blue"
        popup = f"{n}. {name}"
    folium.Marker([lat, lon], popup=popup, icon=folium.Icon(color=color)).add_to(route_map)
    coords.append((lat, lon))

# Original route polyline
folium.PolyLine(coords, weight=5, color="orange", opacity=0.8, tooltip="Optimized Route").add_to(route_map)

# Optional: Round-trip polyline if start == end
if round_trip:
    folium.PolyLine(list(reversed(coords)), weight=5, color="purple", opacity=0.5, tooltip="Return Trip").add_to(route_map)

route_map.save(OUTPUT_HTML)
print("\nMap saved as:", OUTPUT_HTML)
