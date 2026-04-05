from django.urls import path
from .views import (
    InitiateCallView, IceConfigView, EndCallView,
    DeclineCallView, CallHistoryView, ActiveCallView,
)

urlpatterns = [
    path("initiate/",                    InitiateCallView.as_view(),  name="call-initiate"),
    path("ice-config/<uuid:room_id>/",   IceConfigView.as_view(),     name="call-ice-config"),
    path("<uuid:room_id>/end/",          EndCallView.as_view(),       name="call-end"),
    path("<uuid:room_id>/decline/",      DeclineCallView.as_view(),   name="call-decline"),
    path("history/",                     CallHistoryView.as_view(),   name="call-history"),
    path("active/",                      ActiveCallView.as_view(),    name="call-active"),
]
