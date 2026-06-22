"""
Hours-of-Service (HOS) simulation engine.

Builds a minute-accurate duty-status timeline for a trip (current location ->
pickup -> dropoff) for a property-carrying driver under the 70-hour/8-day
rule set, with these operating parameters:

    - Property-carrying driver, 70 hrs / 8 days, no adverse driving conditions
    - Fuel stop at least once every 1,000 miles
    - 1 hour each for pickup and drop-off

Regulations modeled (49 CFR Part 395):
    - 11-hour driving limit per duty period
    - 14-hour on-duty "window" per duty period (wall-clock, not pausable)
    - 30-minute break required after 8 cumulative hours of driving
    - 10 consecutive hours off duty (or qualifying sleeper berth time)
      required to start a new duty period / reset the 11 & 14 hour clocks
    - 70-hour/8-day on-duty limit; a 34-consecutive-hour break resets it

Cycle tracking: the 70-hour limit is tracked as a running total seeded by
`current_cycle_used_hours`, rather than a full rolling 8-day lookback over
prior trips. A 34-hour restart is inserted automatically if the running
total would otherwise exceed 70 hours.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .routing import point_along_geometry
from .geocoding import reverse_geocode

# --- Regulatory constants (hours unless noted) ---------------------------
MAX_DRIVING_PER_PERIOD = 11.0
MAX_WINDOW_PER_PERIOD = 14.0
DRIVING_BEFORE_BREAK_REQUIRED = 8.0
BREAK_DURATION = 0.5
DAILY_RESET_HOURS = 10.0
CYCLE_LIMIT_HOURS = 70.0
RESTART_HOURS = 34.0
FUEL_INTERVAL_MILES = 1000.0
FUEL_STOP_DURATION = 0.5
PICKUP_DURATION = 1.0
DROPOFF_DURATION = 1.0

EPS = 1e-6


@dataclass
class DutySegment:
    start: datetime
    end: datetime
    status: str  # "OFF_DUTY" | "SLEEPER_BERTH" | "DRIVING" | "ON_DUTY_NOT_DRIVING"
    label: str
    location: list  # [lat, lon]
    miles: float = 0.0

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0


@dataclass
class Stop:
    kind: str
    label: str
    time: datetime
    location: list


@dataclass
class _SimState:
    clock: datetime
    window_start: datetime
    driving_hours_in_period: float = 0.0
    driving_hours_since_break: float = 0.0
    cycle_hours: float = 0.0
    miles_since_fuel: float = 0.0
    total_miles: float = 0.0
    segments: list = field(default_factory=list)
    stops: list = field(default_factory=list)


class HOSSimulator:
    def __init__(self, start_time: datetime, current_cycle_used_hours: float):
        self.state = _SimState(
            clock=start_time,
            window_start=start_time,
            cycle_hours=current_cycle_used_hours,
        )

    # -- internal helpers ---------------------------------------------
    def _hours_into_window(self) -> float:
        return (self.state.clock - self.state.window_start).total_seconds() / 3600.0

    def _add_segment(self, duration_hours, status, label, location, miles=0.0):
        s = self.state
        start = s.clock
        end = start + timedelta(hours=duration_hours)
        s.segments.append(
            DutySegment(start=start, end=end, status=status, label=label,
                        location=location, miles=miles)
        )
        s.clock = end

    def _record_stop(self, kind, label, location):
        self.state.stops.append(
            Stop(kind=kind, label=label, time=self.state.clock, location=location)
        )

    def _do_break(self, location, label="30-min break"):
        self._record_stop("break", label, location)
        self._add_segment(BREAK_DURATION, "OFF_DUTY", label, location)
        self.state.driving_hours_since_break = 0.0

    def _do_fuel_stop(self, location, label="Fuel"):
        self._record_stop("fuel", label, location)
        self._add_segment(FUEL_STOP_DURATION, "ON_DUTY_NOT_DRIVING", label, location)
        self.state.cycle_hours += FUEL_STOP_DURATION
        self.state.driving_hours_since_break = 0.0
        self.state.miles_since_fuel = 0.0

    def _do_daily_reset(self, location, label="10-hr break (sleeper berth)"):
        self._record_stop("rest", label, location)
        self._add_segment(DAILY_RESET_HOURS, "SLEEPER_BERTH", label, location)
        self.state.driving_hours_in_period = 0.0
        self.state.driving_hours_since_break = 0.0
        self.state.window_start = self.state.clock

    def _do_restart(self, location, label="34-hr restart"):
        self._record_stop("restart", label, location)
        self._add_segment(RESTART_HOURS, "OFF_DUTY", label, location)
        self.state.driving_hours_in_period = 0.0
        self.state.driving_hours_since_break = 0.0
        self.state.cycle_hours = 0.0
        self.state.window_start = self.state.clock

    def _stop_at(self, location, label):
        """Record a named, non-driving event location (pickup/dropoff)."""
        self._record_stop("location", label, location)

    # -- public API ------------------------------------------------------
    def consume_on_duty(self, duration_hours, label, location):
        """Add a fixed-length on-duty, non-driving activity (pickup/dropoff),
        inserting a daily reset or 34-hour restart first if the window or
        cycle would otherwise be exceeded.
        """
        remaining = duration_hours
        while remaining > EPS:
            cap_window = MAX_WINDOW_PER_PERIOD - self._hours_into_window()
            cap_cycle = CYCLE_LIMIT_HOURS - self.state.cycle_hours
            if cap_cycle <= EPS:
                self._do_restart(location)
                continue
            if cap_window <= EPS:
                self._do_daily_reset(location)
                continue
            chunk = min(remaining, cap_window, cap_cycle)
            chunk = max(chunk, 0)
            if chunk <= EPS:
                # Shouldn't happen, but avoid infinite loops defensively.
                self._do_daily_reset(location)
                continue
            self._add_segment(chunk, "ON_DUTY_NOT_DRIVING", label, location)
            self.state.cycle_hours += chunk
            self.state.driving_hours_since_break = 0.0
            remaining -= chunk

    def drive_leg(self, distance_miles, duration_hours, geometry, leg_label):
        """Simulate driving a leg of the trip, inserting breaks, daily
        resets, fuel stops, and cycle restarts as the relevant limits are
        hit along the way.
        """
        if duration_hours <= EPS or distance_miles <= EPS:
            return
        avg_speed = distance_miles / duration_hours
        remaining_duration = duration_hours
        distance_done = 0.0

        while remaining_duration > EPS:
            s = self.state
            cap_driving = MAX_DRIVING_PER_PERIOD - s.driving_hours_in_period
            cap_window = MAX_WINDOW_PER_PERIOD - self._hours_into_window()
            cap_break = DRIVING_BEFORE_BREAK_REQUIRED - s.driving_hours_since_break
            cap_cycle = CYCLE_LIMIT_HOURS - s.cycle_hours
            miles_to_fuel = FUEL_INTERVAL_MILES - s.miles_since_fuel
            cap_fuel = miles_to_fuel / avg_speed if avg_speed > 0 else remaining_duration

            caps = {
                "cycle": cap_cycle,
                "window": cap_window,
                "driving": cap_driving,
                "fuel": cap_fuel,
                "break": cap_break,
                "leg_done": remaining_duration,
            }

            # Anything at/below zero must be resolved before driving further.
            if cap_cycle <= EPS:
                loc = point_along_geometry(geometry, distance_done / distance_miles)
                self._do_restart(loc)
                continue
            if cap_window <= EPS or cap_driving <= EPS:
                loc = point_along_geometry(geometry, distance_done / distance_miles)
                self._do_daily_reset(loc)
                continue
            if cap_break <= EPS:
                loc = point_along_geometry(geometry, distance_done / distance_miles)
                self._do_break(loc)
                continue
            if cap_fuel <= EPS:
                loc = point_along_geometry(geometry, distance_done / distance_miles)
                self._do_fuel_stop(loc)
                continue

            drive_hours = min(caps.values())
            drive_hours = max(drive_hours, 0)
            if drive_hours <= EPS:
                # Numerical edge case - force the smallest cap to resolve.
                limiting = min(caps, key=caps.get)
                loc = point_along_geometry(geometry, distance_done / distance_miles)
                if limiting == "cycle":
                    self._do_restart(loc)
                elif limiting in ("window", "driving"):
                    self._do_daily_reset(loc)
                elif limiting == "fuel":
                    self._do_fuel_stop(loc)
                else:
                    self._do_break(loc)
                continue

            seg_distance = drive_hours * avg_speed
            start_loc = point_along_geometry(geometry, distance_done / distance_miles)
            self._add_segment(drive_hours, "DRIVING", leg_label, start_loc, miles=seg_distance)

            s.driving_hours_in_period += drive_hours
            s.driving_hours_since_break += drive_hours
            s.cycle_hours += drive_hours
            s.miles_since_fuel += seg_distance
            s.total_miles += seg_distance
            distance_done += seg_distance
            remaining_duration -= drive_hours

            # Resolve whichever limit we just hit (within tolerance), in
            # priority order, before the next loop iteration.
            limiting = min(caps, key=caps.get)
            if limiting == "leg_done":
                break
            loc_now = point_along_geometry(geometry, min(distance_done / distance_miles, 1.0))
            if limiting == "cycle":
                self._do_restart(loc_now)
            elif limiting in ("window", "driving"):
                self._do_daily_reset(loc_now)
            elif limiting == "fuel":
                self._do_fuel_stop(loc_now)
            elif limiting == "break":
                self._do_break(loc_now)


def simulate_trip(start_time, current_cycle_used_hours, leg_to_pickup, leg_to_dropoff,
                   current_label, pickup_label, dropoff_label):
    """Run the full simulation for current -> pickup -> dropoff and return
    the raw segments/stops. `leg_to_pickup` / `leg_to_dropoff` are routing
    results from `services.routing.get_route`.
    """
    sim = HOSSimulator(start_time, current_cycle_used_hours)

    start_loc = leg_to_pickup["geometry"][0] if leg_to_pickup["geometry"] else [0, 0]
    sim._stop_at(start_loc, f"Depart {current_label}")

    sim.drive_leg(
        leg_to_pickup["distance_miles"],
        leg_to_pickup["duration_hours"],
        leg_to_pickup["geometry"],
        "Driving",
    )

    pickup_loc = leg_to_pickup["geometry"][-1] if leg_to_pickup["geometry"] else [0, 0]
    sim._stop_at(pickup_loc, f"Arrive {pickup_label}")
    sim.consume_on_duty(PICKUP_DURATION, "Pickup", pickup_loc)

    sim.drive_leg(
        leg_to_dropoff["distance_miles"],
        leg_to_dropoff["duration_hours"],
        leg_to_dropoff["geometry"],
        "Driving",
    )

    dropoff_loc = leg_to_dropoff["geometry"][-1] if leg_to_dropoff["geometry"] else [0, 0]
    sim._stop_at(dropoff_loc, f"Arrive {dropoff_label}")
    sim.consume_on_duty(DROPOFF_DURATION, "Delivery", dropoff_loc)

    return sim.state.segments, sim.state.stops, sim.state.total_miles


def enrich_stops_with_city_labels(stops, max_lookups=30):
    """Reverse-geocode stop locations into short 'City, ST' labels for
    display, capped to avoid excessive API calls on very long trips.
    """
    enriched = []
    for i, stop in enumerate(stops):
        if i < max_lookups:
            city_label = reverse_geocode(stop.location[0], stop.location[1])
        else:
            city_label = f"{stop.location[0]:.2f}, {stop.location[1]:.2f}"
        enriched.append({
            "kind": stop.kind,
            "label": stop.label,
            "city": city_label,
            "time": stop.time.isoformat(),
            "location": stop.location,
        })
    return enriched
