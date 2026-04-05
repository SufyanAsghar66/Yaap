from django.urls import path
from .views import (
    VoiceSentencesView,
    VoiceSampleUploadView,
    VoiceSampleDeleteView,
    VoiceTrainView,
    VoiceStatusView,
    VoiceResetView,
)

urlpatterns = [
    path("sentences/",              VoiceSentencesView.as_view(),      name="voice-sentences"),
    path("samples/",                VoiceSampleUploadView.as_view(),   name="voice-sample-upload"),
    path("samples/<int:sample_index>/", VoiceSampleDeleteView.as_view(), name="voice-sample-delete"),
    path("train/",                  VoiceTrainView.as_view(),          name="voice-train"),
    path("status/",                 VoiceStatusView.as_view(),         name="voice-status"),
    path("reset/",                  VoiceResetView.as_view(),          name="voice-reset"),
]
