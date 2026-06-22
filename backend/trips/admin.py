from django.contrib import admin

from .models import DailyLog, DailyLogRemark, DailyLogSegment, Trip, TripStop


class TripStopInline(admin.TabularInline):
    model = TripStop
    extra = 0


class DailyLogInline(admin.TabularInline):
    model = DailyLog
    extra = 0
    show_change_link = True


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("id", "current_location", "pickup_location", "dropoff_location",
                     "total_miles", "total_days", "created_at")
    list_filter = ("created_at",)
    search_fields = ("current_location", "pickup_location", "dropoff_location")
    inlines = [TripStopInline, DailyLogInline]

    def get_queryset(self, request):
        # Avoid N+1 lookups when the inlines render for the change list/form.
        return super().get_queryset(request).prefetch_related("stops", "daily_logs")


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ("id", "trip", "date", "total_hours", "miles_today")
    list_select_related = ("trip",)
