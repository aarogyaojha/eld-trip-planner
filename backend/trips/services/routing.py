"""
Routing helpers built on the public OSRM demo server
(https://project-osrm.org/). No API key required.

For higher-volume production traffic, point OSRM_BASE_URL at a self-hosted
OSRM instance or swap this module for a paid provider with an SLA.
"""
import requests

OSRM_BASE_URL = "https://router.project-osrm.org"

METERS_PER_MILE = 1609.34


class RoutingError(Exception):
    """Raised when a route can't be computed between two points."""


def get_route(origin: dict, destination: dict) -> dict:
    """Get a driving route between two {"lat", "lon"} points.

    Returns a dict with:
        distance_miles: float
        duration_hours: float
        geometry: list[[lat, lon], ...]  (decoded GeoJSON coordinates)
    """
    coords = f"{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}"
    try:
        response = requests.get(
            f"{OSRM_BASE_URL}/route/v1/driving/{coords}",
            params={"overview": "full", "geometries": "geojson"},
            headers={"User-Agent": "eld-trip-planner/1.0 (contact: ops@eld-trip-planner.example)"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RoutingError(f"Could not reach the routing service: {exc}") from exc

    # OSRM returns a 400 status (with a JSON body explaining why) when no
    # driving route exists between the two points - e.g. they're separated
    # by an ocean, or one of them isn't actually reachable by road. We want
    # to surface that as a friendly RoutingError rather than a raw 400/500
    # crash, so we parse the body before checking the HTTP status.
    try:
        data = response.json()
    except ValueError:
        raise RoutingError(
            "The routing service returned an unexpected response. Please try again."
        )

    if data.get("code") != "Ok" or not data.get("routes"):
        reason = data.get("message") or data.get("code") or "no route found"
        raise RoutingError(
            "Could not find a driving route between these two locations "
            f"({reason}). Make sure both are reachable by road on the same "
            "landmass - OSRM can't route across oceans or unconnected regions."
        )

    route = data["routes"][0]
    # OSRM returns GeoJSON coordinates as [lon, lat]. Leaflet expects [lat, lon].
    # So we flip them here before sending to the frontend.
    geometry = [[lat, lon] for lon, lat in route["geometry"]["coordinates"]]

    return {
        "distance_miles": route["distance"] / METERS_PER_MILE,
        "duration_hours": route["duration"] / 3600.0,
        "geometry": geometry,
    }


def point_along_geometry(geometry: list, fraction: float) -> list:
    """Approximate the point at `fraction` (0-1) of the way along a route's
    geometry (list of [lat, lon]), using cumulative straight-line distance
    between vertices. Good enough for placing stop markers and labeling
    remarks - not used for actual routing math.
    """
    if not geometry:
        return [0, 0]
    if fraction <= 0:
        return geometry[0]
    if fraction >= 1:
        return geometry[-1]

    def haversine(p1, p2):
        import math

        lat1, lon1, lat2, lon2 = map(math.radians, [p1[0], p1[1], p2[0], p2[1]])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * 6371 * math.asin(math.sqrt(a))

    segment_lengths = [
        haversine(geometry[i], geometry[i + 1]) for i in range(len(geometry) - 1)
    ]
    total = sum(segment_lengths)
    if total == 0:
        return geometry[0]
    target = fraction * total

    covered = 0.0
    for i, seg_len in enumerate(segment_lengths):
        if covered + seg_len >= target:
            remaining = target - covered
            seg_fraction = remaining / seg_len if seg_len else 0
            p1, p2 = geometry[i], geometry[i + 1]
            return [
                p1[0] + (p2[0] - p1[0]) * seg_fraction,
                p1[1] + (p2[1] - p1[1]) * seg_fraction,
            ]
        covered += seg_len
    return geometry[-1]
