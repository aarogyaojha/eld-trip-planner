# Freightline — Route + HOS Log Planner

Plans a truck route (current location → pickup → drop-off) and generates
compliant FMCSA Driver's Daily Log sheets for the trip, with a map of every
stop the route requires.

**Stack:** Django + Django REST Framework (backend) · React + Vite (frontend)
**Maps/Routing:** Local City Database (autocomplete) + OSRM (routing) + Nominatim (fallback geocoding). No API keys required. Rendered with Leaflet on a CARTO dark basemap.

## What it does

Given a current location, pickup, drop-off, and hours already used in the
70-hour/8-day cycle, it:

1. Look up coordinates for the three locations and routes between them.
2. Runs an Hours-of-Service simulation that inserts every break, rest, fuel
   stop, and cycle restart the regulations require along the way.
3. Splits the resulting duty timeline into one 24-hour log sheet per day,
   fully filled out — duty-status grid, daily totals, and remarks (city/state
   + activity at each status change).
4. Persists the trip so it can be revisited from the trip history panel
   without re-hitting the routing/geocoding APIs.

## Regulations modeled

11-hour driving limit, 14-hour on-duty window, 30-minute break after 8 hours
of cumulative driving, 10-consecutive-hour resets, the 70-hour/8-day limit
with 34-hour restart. See `backend/trips/services/hos.py` for the full state
machine.

**Operating parameters:** property-carrying driver, 70-hour/8-day cycle, no
adverse driving conditions, a fuel stop at least every 1,000 miles, 1 hour
each for pickup and drop-off. The 70-hour cycle is tracked as a running
total seeded by the cycle-hours input rather than a full rolling 8-day
lookback over prior trips.

## Project layout

```
eld-trip-planner/
├── backend/
│   ├── worldcities.csv        City database for fast, offline autocomplete
│   ├── eld_planner/           settings, urls (env-driven)
│   └── trips/
│       ├── views.py           plan-trip, trip list/detail endpoints
│       ├── serializers.py     request validation + response shapes
│       ├── exceptions.py      DRF exception handler (no leaked internals)
│       ├── models.py          Trip / TripStop / DailyLog / Segment / Remark / City
│       └── services/
│           ├── geocoding.py   City model queries + Nominatim fallback
│           ├── routing.py     OSRM wrapper (fetches pathing/distance/duration)
│           ├── hos.py         HOS simulation engine
│           └── logsheets.py   Splits the timeline into daily log sheets
└── frontend/
    └── src/
        ├── App.jsx
        ├── api.js
        └── components/
            ├── TripForm.jsx
            ├── LocationAutocomplete.jsx
            ├── RouteMap.jsx
            ├── ELDLogSheet.jsx
            ├── DailyLogsView.jsx
            └── TripHistory.jsx
```

## API

- `POST /api/plan-trip/` — plan a trip, returns route + stops + daily logs
  and persists it. (Optimized: coordinates can be passed directly from autocomplete to bypass fallback geocoding.)
- `GET /api/locations/suggest/?q=` — fast city/place autocomplete querying the local database.
- `GET /api/trips/` — paginated trip history (summary fields only).
- `GET /api/trips/<id>/` — full trip detail, including stops and daily logs.

## Security

- All config (secret key, allowed hosts, CORS origins, database URL) comes
  from environment variables — see `.env.example`.
- Every API response goes through a custom exception handler
  (`trips/exceptions.py`) that never leaks internals (stack traces, etc.).
- Anonymous request throttling (`30/min` by default) on every endpoint.

## Database design (no N+1 queries)

- **Writes:** `_persist_trip()` in `views.py` batches each table into a
  single `bulk_create()` call instead of looping `.create()` per row.
- **Reads:** `GET /api/trips/<id>/` uses `prefetch_related()`, which executes a fixed number of queries regardless of how many stops or daily logs a trip has.

## Running locally

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit as needed
python manage.py migrate

# Load the local city database for the autocomplete endpoint
python manage.py load_cities

python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`.

## Deploying

**Backend → Render (free Web Service):**
1. Push to GitHub, connect the repo, root directory `backend`.
2. Build Command: `pip install -r requirements.txt && python manage.py migrate && python manage.py load_cities`
3. Start Command: `gunicorn eld_planner.wsgi:application --bind 0.0.0.0:$PORT`
4. Env vars: `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY=<random>`,
   `DJANGO_ALLOWED_HOSTS=<render-domain>`,
   `CORS_ALLOWED_ORIGINS=https://<vercel-domain>`,
   `DATABASE_URL=<a free Postgres instance>` (Render's filesystem is wiped
   on every deploy, so SQLite won't persist trip history there).

**Frontend → Vercel:**
1. Import the repo, root directory `frontend`, framework preset Vite.
2. Env var: `VITE_API_BASE_URL=https://<render-domain>/api`.

## Notes for Future Devs

- **Mapping/Routing:** The app currently relies on the public OSRM demonstration server (`router.project-osrm.org`) for routing. While acceptable for development, this server is rate-limited and lacks any Service Level Agreement (SLA). For a production rollout, swap `OSRM_BASE_URL` in `trips/services/routing.py` to a self-hosted OSRM instance or a commercial alternative (Mapbox, Google Maps, OpenRouteService).
- **Coordinate Systems:** The backend receives GeoJSON geometries (`[lon, lat]`) from OSRM. Note that Leaflet expects geometries as `[lat, lon]`. The backend specifically flips this array in `routing.py` before serving the payload to the frontend.
- **City Search Database:** The local database uses the Simplemaps World Cities dataset. It is populated via the custom management command `load_cities`. Update the underlying `worldcities.csv` if geographical boundaries or populations drastically shift in the future.
