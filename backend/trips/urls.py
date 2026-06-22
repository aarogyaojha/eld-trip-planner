from django.urls import path

from .views import TripDetailView, TripListView, plan_trip, suggest_locations

urlpatterns = [
    path("plan-trip/", plan_trip, name="plan-trip"),
    path("locations/suggest/", suggest_locations, name="suggest-locations"),
    path("trips/", TripListView.as_view(), name="trip-list"),
    path("trips/<int:pk>/", TripDetailView.as_view(), name="trip-detail"),
]
