from django.db import models


class City(models.Model):
    name = models.CharField(max_length=255)
    state_name = models.CharField(max_length=255, blank=True)
    state_id = models.CharField(max_length=10, blank=True)
    country_name = models.CharField(max_length=255, blank=True)
    lat = models.FloatField()
    lng = models.FloatField()
    population = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-population"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["state_name"]),
        ]

    def __str__(self):
        parts = [self.name]
        if self.state_name:
            parts.append(self.state_name)
        if self.country_name:
            parts.append(self.country_name)
        return ", ".join(parts)


class Trip(models.Model):
    """A planned trip, snapshotted at the time it was computed.

    Route geometry and resolved coordinates are stored as JSON rather than
    re-derived on every read, so revisiting a past trip never re-hits the
    geocoding/routing APIs.
    """

    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    current_cycle_used_hours = models.FloatField()

    total_miles = models.FloatField()
    total_days = models.PositiveSmallIntegerField()
    estimated_start = models.DateTimeField()
    estimated_end = models.DateTimeField(null=True, blank=True)

    locations = models.JSONField()
    route_geometry = models.JSONField()
    assumptions = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.current_location} -> {self.pickup_location} -> {self.dropoff_location}"


class TripStop(models.Model):
    KIND_CHOICES = [
        ("location", "Location"),
        ("break", "30-minute break"),
        ("fuel", "Fuel stop"),
        ("rest", "10-hour rest"),
        ("restart", "34-hour restart"),
    ]

    trip = models.ForeignKey(Trip, related_name="stops", on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    label = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    time = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["time"]
        indexes = [models.Index(fields=["trip", "time"])]


class DailyLog(models.Model):
    trip = models.ForeignKey(Trip, related_name="daily_logs", on_delete=models.CASCADE)
    date = models.DateField()
    totals = models.JSONField()
    total_hours = models.FloatField()
    miles_today = models.FloatField()

    class Meta:
        ordering = ["date"]
        unique_together = [("trip", "date")]
        indexes = [models.Index(fields=["trip", "date"])]


class DailyLogSegment(models.Model):
    daily_log = models.ForeignKey(DailyLog, related_name="segments", on_delete=models.CASCADE)
    status = models.CharField(max_length=30)
    start_hr = models.FloatField()
    end_hr = models.FloatField()
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ["start_hr"]
        indexes = [models.Index(fields=["daily_log"])]


class DailyLogRemark(models.Model):
    daily_log = models.ForeignKey(DailyLog, related_name="remarks", on_delete=models.CASCADE)
    time_hr = models.FloatField()
    text = models.CharField(max_length=255)

    class Meta:
        ordering = ["time_hr"]
        indexes = [models.Index(fields=["daily_log"])]
