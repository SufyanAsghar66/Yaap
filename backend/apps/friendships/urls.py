from django.urls import path
from .views import (
    FriendsListView,
    FriendDetailView,
    SendFriendRequestView,
    ReceivedFriendRequestsView,
    SentFriendRequestsView,
    AcceptFriendRequestView,
    DeclineFriendRequestView,
    CancelFriendRequestView,
    BlockUserView,
    UnblockUserView,
    BlockedUsersView,
    RegisterDeviceView,
    FriendSuggestionsView,
)

# This code block defines the URL patterns for a Django application. Each `path` function call maps a
# URL pattern to a specific view class. Here's a breakdown of what each URL pattern is doing:
urlpatterns = [
    # ─── Friends ────────────────────────────────────────────────────────────
    path("",                                FriendsListView.as_view(),           name="friends-list"),
    path("<uuid:friendship_id>/",           FriendDetailView.as_view(),          name="friend-detail"),
    path("suggestions/",                    FriendSuggestionsView.as_view(),     name="friend-suggestions"),

    # ─── Friend Requests ────────────────────────────────────────────────────
    path("request/",                        SendFriendRequestView.as_view(),     name="friend-request-send"),
    path("requests/received/",              ReceivedFriendRequestsView.as_view(), name="friend-requests-received"),
    path("requests/sent/",                  SentFriendRequestsView.as_view(),    name="friend-requests-sent"),
    path("requests/<uuid:request_id>/accept/",  AcceptFriendRequestView.as_view(),  name="friend-request-accept"),
    path("requests/<uuid:request_id>/decline/", DeclineFriendRequestView.as_view(), name="friend-request-decline"),
    path("requests/<uuid:request_id>/",     CancelFriendRequestView.as_view(),  name="friend-request-cancel"),

    # ─── Block ──────────────────────────────────────────────────────────────
    path("block/",                          BlockUserView.as_view(),             name="user-block"),
    path("block/<uuid:user_id>/",           UnblockUserView.as_view(),           name="user-unblock"),
    path("blocked/",                        BlockedUsersView.as_view(),          name="blocked-list"),
    # ─── Devices (FCM) ──────────────────────────────────────────────────────
    path("devices/",                        RegisterDeviceView.as_view(),        name="device-register"),
]
