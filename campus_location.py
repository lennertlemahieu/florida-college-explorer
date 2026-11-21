"""Offline ZIP lookup and campus routing."""

import csv
import gzip
import json
import math
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

import requests

CENSUS_SOURCE = "https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2024.html"
ROUTING_URL = "https://valhalla1.openstreetmap.de/route"


@lru_cache(maxsize=1)
def zip_centroids():
    path = Path(__file__).with_name("data") / "us_zip_centroids.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
        return {row["zip"]: (float(row["lat"]), float(row["lon"])) for row in csv.DictReader(source)}


def miles_between(origin, latitude, longitude):
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return float("nan")
    start_lat, start_lon = map(math.radians, origin)
    end_lat, end_lon = map(math.radians, (latitude, longitude))
    haversine = math.sin((end_lat - start_lat) / 2) ** 2
    haversine += math.cos(start_lat) * math.cos(end_lat) * math.sin((end_lon - start_lon) / 2) ** 2
    return 3958.76 * 2 * math.asin(min(1, math.sqrt(haversine)))


def driving_url(school, zip_code=""):
    query = {"api": 1, "destination": f"{school['lat']},{school['lon']}", "travelmode": "driving"}
    if zip_code:
        query["origin"] = f"{zip_code}, USA"
    return "https://www.google.com/maps/dir/?" + urlencode(query)


class DrivingRouteError(Exception):
    """The routing service could not return a usable path."""


def shortest_driving_route(origin, destination):
    """Return the shortest road route, in Leaflet coordinate order."""
    query = {
        "locations": [{"lat": lat, "lon": lon} for lat, lon in (origin, destination)],
        "costing": "auto",
        "costing_options": {"auto": {"shortest": True}},
        "format": "osrm",
        "shape_format": "geojson",
        "directions_type": "none",
    }
    try:
        response = requests.get(ROUTING_URL, params={"json": json.dumps(query, separators=(",", ":"))},
                                headers={"X-Client-Id": "florida-campus-atlas"}, timeout=(4, 16))
        response.raise_for_status()
        route = response.json()["routes"][0]
        points = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
        miles = route["distance"] / 1609.344
        minutes = route["duration"] / 60
        if len(points) < 2 or not all(math.isfinite(value) and value >= 0 for value in (miles, minutes)):
            raise ValueError("Invalid route")
        if not all(-90 <= lat <= 90 and -180 <= lon <= 180 for lat, lon in points):
            raise ValueError("Invalid coordinates")
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
        raise DrivingRouteError("The driving route is unavailable right now. You can open directions in Google Maps.") from error
    return {"points": points, "miles": miles, "minutes": minutes}
