import logging
from datetime import datetime, timezone

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework import status as http_status

from .models import DailyLog, DailyLogRemark, DailyLogSegment, Trip, TripStop
from .serializers import (
    TripDetailSerializer,
    TripListSerializer,
    TripRequestSerializer,
)
from .services.geocoding import GeocodingError, geocode, search_suggestions
from .services.hos import enrich_stops_with_city_labels, simulate_trip
from .services.logsheets import build_daily_logs
from .services.routing import RoutingError, get_route

logger = logging.getLogger("trips")


@api_view(["GET"])
def suggest_locations(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 3:
        return Response([])
    results = search_suggestions(query)
    return Response(results)


@api_view(["POST"])
def plan_trip(request):
    serializer = TripRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        current = data.get("current_coords") or geocode(data["current_location"])
        pickup = data.get("pickup_coords") or geocode(data["pickup_location"])
        dropoff = data.get("dropoff_coords") or geocode(data["dropoff_location"])
    except GeocodingError as exc:
        return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

    try:
        leg_to_pickup = get_route(current, pickup)
        leg_to_dropoff = get_route(pickup, dropoff)
    except RoutingError as exc:
        return Response({"detail": str(exc)}, status=http_status.HTTP_502_BAD_GATEWAY)

    start_time = datetime.now(timezone.utc)

    segments, stops, total_miles = simulate_trip(
        start_time=start_time,
        current_cycle_used_hours=data["current_cycle_used_hours"],
        leg_to_pickup=leg_to_pickup,
        leg_to_dropoff=leg_to_dropoff,
        current_label=data["current_location"],
        pickup_label=data["pickup_location"],
        dropoff_label=data["dropoff_location"],
    )

    daily_logs = build_daily_logs(segments, total_miles)
    stops_payload = enrich_stops_with_city_labels(stops)

    full_geometry = leg_to_pickup["geometry"] + leg_to_dropoff["geometry"]
    assumptions = [
        "Property-carrying driver on the 70-hour/8-day on-duty limit",
        "No adverse driving conditions",
        "Fuel stop scheduled at least once every 1,000 miles",
        "1 hour allotted for pickup and 1 hour for drop-off",
    ]

    try:
        trip_id = _persist_trip(
            data=data,
            current=current,
            pickup=pickup,
            dropoff=dropoff,
            leg_to_pickup=leg_to_pickup,
            leg_to_dropoff=leg_to_dropoff,
            full_geometry=full_geometry,
            total_miles=total_miles,
            daily_logs=daily_logs,
            stops_payload=stops_payload,
            assumptions=assumptions,
            start_time=start_time,
            end_time=segments[-1].end if segments else None,
        )
    except Exception:
        # Persistence is an audit/history feature, not the core product -
        # a save failure should never prevent the driver from getting their
        # trip plan back.
        logger.exception("Failed to persist trip; returning plan without history.")
        trip_id = None

    response = {
        "trip_id": trip_id,
        "route": {
            "geometry": full_geometry,
            "leg_to_pickup_geometry": leg_to_pickup["geometry"],
            "leg_to_dropoff_geometry": leg_to_dropoff["geometry"],
            "distance_miles": round(leg_to_pickup["distance_miles"] + leg_to_dropoff["distance_miles"], 1),
            "driving_duration_hours": round(
                leg_to_pickup["duration_hours"] + leg_to_dropoff["duration_hours"], 2
            ),
        },
        "locations": {"current": current, "pickup": pickup, "dropoff": dropoff},
        "stops": stops_payload,
        "daily_logs": daily_logs,
        "trip_summary": {
            "total_miles": round(total_miles, 1),
            "total_days": len(daily_logs),
            "estimated_start": start_time.isoformat(),
            "estimated_end": segments[-1].end.isoformat() if segments else None,
        },
        "assumptions": assumptions,
    }
    return Response(response)


def _persist_trip(*, data, current, pickup, dropoff, leg_to_pickup, leg_to_dropoff,
                   full_geometry, total_miles, daily_logs, stops_payload, assumptions,
                   start_time, end_time):
    """Persist the computed trip in a fixed, small number of queries
    regardless of how many stops/days/segments/remarks it has, by batching
    each related table into a single bulk_create() rather than looping
    .create() per row (which would otherwise be an O(n) round trip per
    table - a classic N+1 write pattern).
    """
    with transaction.atomic():
        trip = Trip.objects.create(
            current_location=data["current_location"],
            pickup_location=data["pickup_location"],
            dropoff_location=data["dropoff_location"],
            current_cycle_used_hours=data["current_cycle_used_hours"],
            total_miles=total_miles,
            total_days=len(daily_logs),
            estimated_start=start_time,
            estimated_end=end_time,
            locations={"current": current, "pickup": pickup, "dropoff": dropoff},
            route_geometry={
                "geometry": full_geometry,
                "leg_to_pickup_geometry": leg_to_pickup["geometry"],
                "leg_to_dropoff_geometry": leg_to_dropoff["geometry"],
                "distance_miles": leg_to_pickup["distance_miles"] + leg_to_dropoff["distance_miles"],
                "driving_duration_hours": leg_to_pickup["duration_hours"] + leg_to_dropoff["duration_hours"],
            },
            assumptions=assumptions,
        )

        if stops_payload:
            TripStop.objects.bulk_create([
                TripStop(
                    trip=trip,
                    kind=s["kind"],
                    label=s["label"],
                    city=s["city"],
                    time=s["time"],
                    latitude=s["location"][0],
                    longitude=s["location"][1],
                )
                for s in stops_payload
            ])

        if daily_logs:
            day_objects = DailyLog.objects.bulk_create([
                DailyLog(
                    trip=trip,
                    date=day["date"],
                    totals=day["totals"],
                    total_hours=day["total_hours"],
                    miles_today=day["miles_today"],
                )
                for day in daily_logs
            ])

            segment_rows = []
            remark_rows = []
            for day_obj, day in zip(day_objects, daily_logs):
                segment_rows.extend(
                    DailyLogSegment(
                        daily_log=day_obj,
                        status=seg["status"],
                        start_hr=seg["start_hr"],
                        end_hr=seg["end_hr"],
                        label=seg["label"],
                    )
                    for seg in day["segments"]
                )
                remark_rows.extend(
                    DailyLogRemark(daily_log=day_obj, time_hr=r["time_hr"], text=r["text"])
                    for r in day["remarks"]
                )

            if segment_rows:
                DailyLogSegment.objects.bulk_create(segment_rows)
            if remark_rows:
                DailyLogRemark.objects.bulk_create(remark_rows)

        return trip.id


class TripListView(ListAPIView):
    """GET /api/trips/ - paginated trip history, summary fields only.

    Single query: no related tables are touched, so this stays O(1) queries
    no matter how many stops/days a given trip has.
    """

    serializer_class = TripListSerializer
    queryset = Trip.objects.all()


class TripDetailView(RetrieveAPIView):
    """GET /api/trips/<id>/ - full trip detail.

    `prefetch_related` resolves stops and daily-log segments/remarks in a
    fixed number of additional queries (one per relation), not one query
    per row - this is what keeps a trip with 40 stops and 6 days of logs
    just as cheap to fetch as one with 2 stops and a single day.
    """

    serializer_class = TripDetailSerializer
    queryset = Trip.objects.prefetch_related(
        "stops",
        "daily_logs__segments",
        "daily_logs__remarks",
    )

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
