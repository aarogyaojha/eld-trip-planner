from rest_framework import serializers

from .models import DailyLog, DailyLogRemark, DailyLogSegment, Trip, TripStop


class CoordinateSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    label = serializers.CharField(max_length=255)

class TripRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=255, trim_whitespace=True)
    pickup_location = serializers.CharField(max_length=255, trim_whitespace=True)
    dropoff_location = serializers.CharField(max_length=255, trim_whitespace=True)
    
    current_coords = CoordinateSerializer(required=False, allow_null=True)
    pickup_coords = CoordinateSerializer(required=False, allow_null=True)
    dropoff_coords = CoordinateSerializer(required=False, allow_null=True)

    current_cycle_used_hours = serializers.FloatField(min_value=0, max_value=70)

    def validate(self, attrs):
        for field in ("current_location", "pickup_location", "dropoff_location"):
            if not attrs[field].strip():
                raise serializers.ValidationError({field: "This field may not be blank."})
        return attrs


class TripListSerializer(serializers.ModelSerializer):
    """Lightweight representation for the trip history list - no nested
    relations, so listing trips is always exactly one query.
    """

    class Meta:
        model = Trip
        fields = [
            "id",
            "current_location",
            "pickup_location",
            "dropoff_location",
            "total_miles",
            "total_days",
            "created_at",
        ]


class DailyLogRemarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyLogRemark
        fields = ["time_hr", "text"]


class DailyLogSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyLogSegment
        fields = ["status", "start_hr", "end_hr", "label"]


class DailyLogSerializer(serializers.ModelSerializer):
    segments = DailyLogSegmentSerializer(many=True, read_only=True)
    remarks = DailyLogRemarkSerializer(many=True, read_only=True)

    class Meta:
        model = DailyLog
        fields = ["date", "segments", "remarks", "totals", "total_hours", "miles_today"]


class TripStopSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()

    class Meta:
        model = TripStop
        fields = ["kind", "label", "city", "time", "location"]

    def get_location(self, obj):
        return [obj.latitude, obj.longitude]


class TripDetailSerializer(serializers.ModelSerializer):
    """Full trip representation, including nested stops and daily logs.

    The nested `stops`/`daily_logs` relations rely on the view's queryset
    having already called `prefetch_related()` - DRF's ModelSerializer then
    reads from the prefetched cache instead of issuing a query per Trip
    instance, which is what keeps this N+1-free regardless of list size.
    """

    stops = TripStopSerializer(many=True, read_only=True)
    daily_logs = DailyLogSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "current_location",
            "pickup_location",
            "dropoff_location",
            "current_cycle_used_hours",
            "total_miles",
            "total_days",
            "estimated_start",
            "estimated_end",
            "locations",
            "route_geometry",
            "assumptions",
            "stops",
            "daily_logs",
            "created_at",
        ]
