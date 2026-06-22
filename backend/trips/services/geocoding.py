"""
Geocoding helpers built on the free OpenStreetMap Nominatim API.

Nominatim has a strict usage policy for the public endpoint (max ~1 request/
second, a descriptive User-Agent is required, and no heavy bulk usage). That
is more than sufficient for a trip-planning form that geocodes 3 addresses
and reverse-geocodes a handful of stop locations per request.
"""
import logging
import time

import requests

logger = logging.getLogger("trips")

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = "eld-trip-planner/1.0 (contact: ops@eld-trip-planner.example)"

# Nominatim asks for at most 1 request/second from a given client.
_MIN_INTERVAL_SECONDS = 1.05
_last_request_time = 0.0


class GeocodingError(Exception):
    """Raised when an address can't be resolved to coordinates."""


def _throttle():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_INTERVAL_SECONDS:
        time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
    _last_request_time = time.time()


def geocode(address: str) -> dict:
    """Resolve a free-text address to {"lat": float, "lon": float, "label": str}."""
    _throttle()
    try:
        response = requests.get(
            f"{NOMINATIM_BASE_URL}/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        raise GeocodingError(
            f"Could not look up '{address}' right now (geocoding service error: {exc})."
        ) from exc
    if not results:
        raise GeocodingError(f"Could not find a location for '{address}'.")
    result = results[0]
    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "label": result.get("display_name", address),
    }


def search_suggestions(query: str, limit: int = 5) -> list:
    """Look up place suggestions for an autocomplete dropdown.

    Returns a list of {"label": "City, State", "lat": float, "lon": float}
    dicts from the local City database.
    """
    from trips.models import City
    from django.db.models import Q

    query = query.strip()
    if not query:
        return []
        
    STATE_ABBR = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
        'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
        'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
        'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
        'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
        'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
        'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
        'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
        'DC': 'District of Columbia'
    }

    if ',' in query:
        parts = [p.strip() for p in query.split(',')]
        if len(parts) >= 2:
            city_query = parts[0]
            state_query = parts[1]
            
            # Map abbreviation to full state name if found
            if state_query.upper() in STATE_ABBR:
                state_query = STATE_ABBR[state_query.upper()]
                
            qs = City.objects.filter(
                name__icontains=city_query
            ).filter(
                Q(state_name__icontains=state_query) | Q(state_id__icontains=state_query) | Q(country_name__icontains=state_query)
            )
        else:
            qs = City.objects.filter(name__icontains=query)
    else:
        # Check if query is an abbreviation
        search_query = STATE_ABBR.get(query.upper(), query)
        qs = City.objects.filter(
            Q(name__icontains=search_query) | 
            Q(state_name__icontains=search_query) | 
            Q(state_id__icontains=search_query) |
            Q(country_name__icontains=search_query)
        )

    qs = qs.order_by('-population')[:limit]

    suggestions = []
    seen_labels = set()
    for city in qs:
        label = str(city)
        if label in seen_labels:
            continue
        seen_labels.add(label)

        suggestions.append({
            "label": label,
            "lat": float(city.lat),
            "lon": float(city.lng),
        })

    return suggestions


def reverse_geocode(lat: float, lon: float) -> str:
    """Resolve coordinates back to a short 'City, ST' style label.

    Falls back to a generic 'lat, lon' label if the lookup fails - this is
    only used for cosmetic remarks on the generated logs, so it should never
    block trip planning.
    """
    try:
        _throttle()
        response = requests.get(
            f"{NOMINATIM_BASE_URL}/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 10},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        address = data.get("address", {})
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("county")
            or "En route"
        )
        state = address.get("state_code") or address.get("state") or ""
        return f"{city}, {state}".strip(", ")
    except Exception:
        return f"{lat:.2f}, {lon:.2f}"
