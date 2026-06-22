"""
Splits a continuous duty-status timeline (a list of DutySegment) into one
log sheet per calendar day, matching the FMCSA "Driver's Daily Log" grid:
Off Duty / Sleeper Berth / Driving / On Duty (Not Driving), each day
totaling 24 hours, with a remarks list of duty-status changes.
"""
from datetime import datetime, timedelta

from .geocoding import reverse_geocode

STATUS_ORDER = ["OFF_DUTY", "SLEEPER_BERTH", "DRIVING", "ON_DUTY_NOT_DRIVING"]


def _day_start(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def build_daily_logs(segments, total_distance_miles, max_city_lookups=40):
    """Return a list of day dicts ready for the frontend to render as
    log-sheet grids.
    """
    if not segments:
        return []

    trip_start = segments[0].start
    trip_end = segments[-1].end

    days = []
    cursor = _day_start(trip_start)
    end_day = _day_start(trip_end)

    city_lookup_budget = {"count": 0}

    def city_for(location):
        if city_lookup_budget["count"] >= max_city_lookups:
            return f"{location[0]:.2f}, {location[1]:.2f}"
        city_lookup_budget["count"] += 1
        return reverse_geocode(location[0], location[1])

    while cursor <= end_day:
        day_start = cursor
        day_end = cursor + timedelta(days=1)

        day_segments = []
        remarks = []
        totals = {k: 0.0 for k in STATUS_ORDER}
        day_miles = 0.0
        first_overlap_start = None

        for seg in segments:
            overlap_start = max(seg.start, day_start)
            overlap_end = min(seg.end, day_end)
            if overlap_start >= overlap_end:
                continue

            if first_overlap_start is None:
                first_overlap_start = overlap_start

            start_hr = (overlap_start - day_start).total_seconds() / 3600.0
            end_hr = (overlap_end - day_start).total_seconds() / 3600.0
            day_segments.append({
                "status": seg.status,
                "start_hr": round(start_hr, 4),
                "end_hr": round(end_hr, 4),
                "label": seg.label,
            })
            totals[seg.status] += (end_hr - start_hr)

            if seg.status == "DRIVING" and seg.miles:
                fraction_of_segment = (overlap_end - overlap_start) / (seg.end - seg.start)
                day_miles += seg.miles * fraction_of_segment

            if seg.start >= day_start and seg.start < day_end:
                remarks.append({
                    "time_hr": round(start_hr, 2),
                    "text": f"{city_for(seg.location)} - {seg.label}",
                })

        if not day_segments:
            day_segments.append({"status": "OFF_DUTY", "start_hr": 0, "end_hr": 24, "label": "Off duty"})
            totals["OFF_DUTY"] = 24.0
        else:
            first_start = day_segments[0]["start_hr"]
            if first_start > 0:
                day_segments.insert(0, {
                    "status": "OFF_DUTY", "start_hr": 0, "end_hr": first_start, "label": "Off duty",
                })
                totals["OFF_DUTY"] += first_start
            last_end = day_segments[-1]["end_hr"]
            if last_end < 24:
                day_segments.append({
                    "status": "OFF_DUTY", "start_hr": last_end, "end_hr": 24, "label": "Off duty",
                })
                totals["OFF_DUTY"] += (24 - last_end)

        days.append({
            "date": day_start.date().isoformat(),
            "segments": day_segments,
            "remarks": remarks,
            "totals": {k: round(v, 2) for k, v in totals.items()},
            "total_hours": round(sum(totals.values()), 2),
            "miles_today": round(day_miles, 1),
        })

        cursor = day_end

    return days
