"""
Call Celery Tasks

mark_missed_if_unanswered — scheduled 30 s after initiation
  If the callee hasn't answered by then, mark the call MISSED
  and push a missed call notification.

cleanup_stale_calls — periodic beat task (every 5 minutes)
  Finds calls stuck in INITIATED/ANSWERED state for > 2 hours
  and forcibly ends them to prevent stale DB records.
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(name="calls.mark_missed_if_unanswered", queue="default")
def mark_missed_if_unanswered(call_room_id: str):
    """
    Called 30 seconds after call initiation.
    If the call is still in INITIATED state (not answered or declined),
    mark it as MISSED and notify the caller via FCM.
    """
    from apps.calls.models import CallRoom
    try:
        room = CallRoom.objects.select_related("caller", "callee").get(id=call_room_id)
    except CallRoom.DoesNotExist:
        logger.warning("mark_missed: room %s not found", call_room_id)
        return

    if room.status != CallRoom.Status.INITIATED:
        logger.debug("mark_missed: room %s already %s — skip", call_room_id, room.status)
        return

    room.mark_missed()
    logger.info("Call marked MISSED: room=%s caller=%s callee=%s", room.room_id, room.caller_id, room.callee_id)

    # Push missed call notification to caller
    try:
        from apps.friendships.models import UserDevice
        from services.fcm_service import send_push
        tokens = list(UserDevice.objects.filter(user=room.caller).values_list("fcm_token", flat=True))
        for token in tokens:
            send_push(
                device_token      = token,
                title             = "Missed Call",
                body              = f"{room.callee.name} didn't answer.",
                data              = {"type": "missed_call", "room_id": str(room.room_id), "callee_id": str(room.callee_id)},
                notification_type = "call",
            )
    except Exception as e:
        logger.warning("FCM missed call push failed: %s", e)

    # Also notify callee they missed a call
    try:
        from apps.friendships.models import UserDevice
        from services.fcm_service import send_push
        tokens = list(UserDevice.objects.filter(user=room.callee).values_list("fcm_token", flat=True))
        for token in tokens:
            send_push(
                device_token      = token,
                title             = "Missed Call",
                body              = f"You missed a call from {room.caller.name}.",
                data              = {"type": "missed_call", "room_id": str(room.room_id), "caller_id": str(room.caller_id)},
                notification_type = "call",
            )
    except Exception as e:
        logger.warning("FCM missed call callee push failed: %s", e)


@shared_task(name="calls.cleanup_stale_calls", queue="default")
def cleanup_stale_calls():
    """
    Periodic task — ends calls stuck in INITIATED/ANSWERED for > 2 hours.
    Registered in Django Celery Beat via admin or programmatically.
    """
    from apps.calls.models import CallRoom
    cutoff  = timezone.now() - timedelta(hours=2)
    stale   = CallRoom.objects.filter(
        status__in = [CallRoom.Status.INITIATED, CallRoom.Status.ANSWERED],
        started_at__lt = cutoff,
    )
    count = stale.count()
    for room in stale:
        room.end()

    if count:
        logger.warning("cleanup_stale_calls: ended %d stale call(s)", count)
    return {"cleaned": count}
