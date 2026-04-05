from django.urls import path
from apps.accounts.views.user_views import (
    MeView,
    AvatarUploadView,
    LanguagePreferenceView,
    UserDetailView,
    UserSearchView,
    SupportedLanguagesView,
)

urlpatterns = [
    path("me/",                  MeView.as_view(),                name="user-me"),
    path("me/avatar/",           AvatarUploadView.as_view(),      name="user-avatar"),
    path("me/language/",         LanguagePreferenceView.as_view(), name="user-language"),
    path("search/",              UserSearchView.as_view(),         name="user-search"),
    path("languages/",           SupportedLanguagesView.as_view(), name="user-languages"),
    path("<uuid:user_id>/",      UserDetailView.as_view(),         name="user-detail"),
]
