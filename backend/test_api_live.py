#!/usr/bin/env python3
"""
YAAP Live API Test Runner
Tests every endpoint against a running backend server.

Usage:
  # Make sure backend is running first:
  #   ./run.sh start

  python test_api_live.py                    # run all tests
  python test_api_live.py auth               # run only auth tests
  python test_api_live.py friends messaging  # run multiple modules
  python test_api_live.py --base http://10.0.0.5:8000  # custom host

Each test prints PASS / FAIL / SKIP with response details on failure.
At the end a summary table is printed.

Modules: auth, profile, friends, messaging, voice, calls
"""

import sys
import json
import time
import argparse
import traceback
from typing import Optional
import requests

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_BASE = "http://localhost:8000"
TIMEOUT      = 15

# ── Colour helpers ────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
NC     = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓ PASS{NC}  {msg}")
def fail(msg): print(f"  {RED}✗ FAIL{NC}  {msg}")
def skip(msg): print(f"  {YELLOW}- SKIP{NC}  {msg}")
def hdr(msg):  print(f"\n{BOLD}{CYAN}── {msg} ──{NC}")


# ── State shared across tests ─────────────────────────────────────────────────

class State:
    def __init__(self, base: str):
        self.base        = base.rstrip("/")
        self.access      = None
        self.refresh     = None
        self.user_id     = None
        self.user_b_access = None
        self.user_b_id   = None
        self.friendship_id   = None
        self.friend_req_id   = None
        self.conversation_id = None
        self.message_id      = None
        self.voice_sentence_ids = []
        self.call_room_id    = None
        self.results         = []   # (name, passed, note)

    def url(self, path):
        return f"{self.base}{path}"

    def auth_headers(self, token=None):
        t = token or self.access
        return {"Authorization": f"Bearer {t}"} if t else {}

    def record(self, name, passed, note=""):
        status = "PASS" if passed else "FAIL"
        self.results.append((name, status, note))
        if passed:
            ok(name)
        else:
            fail(f"{name}  →  {note}")


# ── Generic request helper ────────────────────────────────────────────────────

def req(method, url, *, headers=None, json_body=None, files=None, data=None,
        expected=None, timeout=TIMEOUT):
    """Make an HTTP request and return (response, ok_bool)."""
    try:
        r = requests.request(
            method, url,
            headers = headers or {},
            json    = json_body,
            files   = files,
            data    = data,
            timeout = timeout,
        )
        if expected:
            passed = r.status_code in (expected if isinstance(expected, (list, tuple)) else [expected])
        else:
            passed = r.status_code < 400
        return r, passed
    except requests.exceptions.ConnectionError:
        return None, False
    except Exception as e:
        return None, False


# ════════════════════════════════════════════════════════════════════════════
# AUTH TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_auth(s: State):
    hdr("AUTH")

    # ── Health check ──────────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/health/"))
    s.record("GET /health/", ok_ and r.status_code == 200,
             f"status={r.status_code if r else 'no response'}")

    # ── Password strength ─────────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/auth/password/strength/"),
                 json_body={"password": "abc"})
    passed = ok_ and r.json().get("data", {}).get("strength", {}).get("level") == "weak"
    s.record("POST /auth/password/strength/ (weak)", passed)

    r, ok_ = req("POST", s.url("/api/v1/auth/password/strength/"),
                 json_body={"password": "SecurePass1!XY"})
    passed = ok_ and r.json().get("data", {}).get("strength", {}).get("level") == "very_strong"
    s.record("POST /auth/password/strength/ (very_strong)", passed)

    # ── Signup ────────────────────────────────────────────────────────────────
    ts = int(time.time())
    r, ok_ = req("POST", s.url("/api/v1/auth/signup/"), json_body={
        "full_name":        "Test Runner",
        "email":            f"runner_{ts}@yaap.test",
        "password":         "RunnerPass1!",
        "password_confirm": "RunnerPass1!",
    })
    if ok_ and r:
        data = r.json().get("data", {})
        s.access  = data.get("tokens", {}).get("access")
        s.refresh = data.get("tokens", {}).get("refresh")
        s.user_id = data.get("user", {}).get("id")
        s.record("POST /auth/signup/", bool(s.access), f"user_id={s.user_id}")
    else:
        s.record("POST /auth/signup/", False, f"status={r.status_code if r else 'no response'}: {r.text[:200] if r else ''}")

    # ── Signup duplicate email ────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/auth/signup/"), json_body={
        "full_name": "Dupe", "email": f"runner_{ts}@yaap.test",
        "password": "Pass1234!", "password_confirm": "Pass1234!",
    }, expected=400)
    s.record("POST /auth/signup/ (duplicate email → 400)", ok_)

    # ── Signup weak password ──────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/auth/signup/"), json_body={
        "full_name": "Weak", "email": f"weak_{ts}@yaap.test",
        "password": "abc", "password_confirm": "abc",
    }, expected=400)
    s.record("POST /auth/signup/ (weak password → 400)", ok_)

    # ── Login ─────────────────────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/auth/login/"), json_body={
        "email": f"runner_{ts}@yaap.test", "password": "RunnerPass1!",
    })
    passed = ok_ and "access" in r.json().get("data", {}).get("tokens", {})
    s.record("POST /auth/login/", passed)

    # ── Login wrong password ──────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/auth/login/"), json_body={
        "email": f"runner_{ts}@yaap.test", "password": "WrongPass!",
    }, expected=400)
    s.record("POST /auth/login/ (wrong password → 400)", ok_)

    # ── Token refresh ─────────────────────────────────────────────────────────
    if s.refresh:
        r, ok_ = req("POST", s.url("/api/v1/auth/token/refresh/"),
                     json_body={"refresh": s.refresh})
        if ok_ and r:
            new_access = r.json().get("data", {}).get("tokens", {}).get("access")
            if new_access:
                s.access = new_access
        s.record("POST /auth/token/refresh/", ok_)
    else:
        skip("Token refresh — no refresh token")

    # ── OTP request ───────────────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/auth/otp/request/"),
                 json_body={"email": f"otp_{ts}@yaap.test"})
    s.record("POST /auth/otp/request/", ok_)

    # ── Sign up user B for friendship tests ───────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/auth/signup/"), json_body={
        "full_name": "User B", "email": f"user_b_{ts}@yaap.test",
        "password": "UserBPass1!", "password_confirm": "UserBPass1!",
    })
    if ok_ and r:
        data = r.json().get("data", {})
        s.user_b_access = data.get("tokens", {}).get("access")
        s.user_b_id     = data.get("user", {}).get("id")
    s.record("POST /auth/signup/ (user B)", ok_ and bool(s.user_b_id))

    # ── Logout ────────────────────────────────────────────────────────────────
    if s.refresh:
        r, ok_ = req("POST", s.url("/api/v1/auth/logout/"),
                     headers=s.auth_headers(),
                     json_body={"refresh": s.refresh})
        s.record("POST /auth/logout/", ok_)
        # Log back in
        r2, _ = req("POST", s.url("/api/v1/auth/login/"), json_body={
            "email": f"runner_{ts}@yaap.test", "password": "RunnerPass1!",
        })
        if r2:
            data = r2.json().get("data", {})
            s.access  = data.get("tokens", {}).get("access")
            s.refresh = data.get("tokens", {}).get("refresh")


# ════════════════════════════════════════════════════════════════════════════
# PROFILE TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_profile(s: State):
    hdr("PROFILE")

    if not s.access:
        skip("Profile — no access token")
        return

    # ── Get own profile ───────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/users/me/"), headers=s.auth_headers())
    passed = ok_ and r.json().get("data", {}).get("id") == s.user_id
    s.record("GET /users/me/", passed)

    # ── Patch profile ─────────────────────────────────────────────────────────
    r, ok_ = req("PATCH", s.url("/api/v1/users/me/"), headers=s.auth_headers(),
                 json_body={"display_name": "RunnerUpdated", "bio": "Test bio",
                            "country_code": "PK", "date_of_birth": "1995-06-15"})
    s.record("PATCH /users/me/", ok_)

    # ── Get supported languages ───────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/users/languages/"), headers=s.auth_headers())
    passed = ok_ and len(r.json().get("data", {}).get("languages", [])) == 17
    s.record("GET /users/languages/ (17 languages)", passed)

    # ── Update language preference ────────────────────────────────────────────
    r, ok_ = req("PATCH", s.url("/api/v1/users/me/language/"), headers=s.auth_headers(),
                 json_body={"language_preference": "ar"})
    s.record("PATCH /users/me/language/", ok_)
    # Reset back to English for other tests
    req("PATCH", s.url("/api/v1/users/me/language/"), headers=s.auth_headers(),
        json_body={"language_preference": "en"})

    # ── Search users ──────────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/users/search/?q=User"), headers=s.auth_headers())
    s.record("GET /users/search/?q=User", ok_)

    # ── Search too short ──────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/users/search/?q=x"), headers=s.auth_headers(),
                 expected=400)
    s.record("GET /users/search/?q=x (too short → 400)", ok_)

    # ── Get other user's profile ──────────────────────────────────────────────
    if s.user_b_id:
        r, ok_ = req("GET", s.url(f"/api/v1/users/{s.user_b_id}/"), headers=s.auth_headers())
        s.record("GET /users/{id}/ (other user)", ok_)


# ════════════════════════════════════════════════════════════════════════════
# FRIENDS TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_friends(s: State):
    hdr("FRIENDS")

    if not s.access or not s.user_b_id:
        skip("Friends — missing tokens or user B")
        return

    # ── Register FCM device ───────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/friends/devices/"), headers=s.auth_headers(),
                 json_body={"fcm_token": "fake-fcm-token-for-testing-12345", "device_name": "Test Device"})
    s.record("POST /friends/devices/", ok_)

    # ── Send friend request ───────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/friends/request/"), headers=s.auth_headers(),
                 json_body={"to_user_id": s.user_b_id, "message": "Hey, let's connect!"})
    if ok_ and r:
        s.friend_req_id = r.json().get("data", {}).get("request", {}).get("id")
    s.record("POST /friends/request/", ok_ and bool(s.friend_req_id))

    # ── Duplicate request should fail ─────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/friends/request/"), headers=s.auth_headers(),
                 json_body={"to_user_id": s.user_b_id}, expected=400)
    s.record("POST /friends/request/ (duplicate → 400)", ok_)

    # ── Sent requests list ────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/friends/requests/sent/"), headers=s.auth_headers())
    passed = ok_ and r.json().get("data", {}).get("count", 0) >= 1
    s.record("GET /friends/requests/sent/", passed)

    # ── Received requests (from user B's perspective) ─────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/friends/requests/received/"),
                 headers=s.auth_headers(s.user_b_access))
    passed = ok_ and r.json().get("data", {}).get("count", 0) >= 1
    s.record("GET /friends/requests/received/ (as user B)", passed)

    # ── Accept friend request ─────────────────────────────────────────────────
    if s.friend_req_id:
        r, ok_ = req("POST", s.url(f"/api/v1/friends/requests/{s.friend_req_id}/accept/"),
                     headers=s.auth_headers(s.user_b_access))
        if ok_ and r:
            s.friendship_id = r.json().get("data", {}).get("friendship_id")
        s.record("POST /friends/requests/{id}/accept/ (as user B)", ok_)

    # ── Friends list ──────────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/friends/"), headers=s.auth_headers())
    passed = ok_ and r.json().get("data", {}).get("count", 0) >= 1
    s.record("GET /friends/", passed)

    # ── Friend suggestions ────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/friends/suggestions/"), headers=s.auth_headers())
    s.record("GET /friends/suggestions/", ok_)

    # ── Block user (create a user C to block) ─────────────────────────────────
    ts = int(time.time())
    r2, _ = req("POST", s.url("/api/v1/auth/signup/"), json_body={
        "full_name": "Block Target", "email": f"block_target_{ts}@yaap.test",
        "password": "BlockPass1!", "password_confirm": "BlockPass1!",
    })
    block_target_id = r2.json().get("data", {}).get("user", {}).get("id") if r2 else None

    if block_target_id:
        r, ok_ = req("POST", s.url("/api/v1/friends/block/"), headers=s.auth_headers(),
                     json_body={"user_id": block_target_id})
        s.record("POST /friends/block/", ok_)

        r, ok_ = req("GET", s.url("/api/v1/friends/blocked/"), headers=s.auth_headers())
        passed = ok_ and r.json().get("data", {}).get("count", 0) >= 1
        s.record("GET /friends/blocked/", passed)

        r, ok_ = req("DELETE", s.url(f"/api/v1/friends/block/{block_target_id}/"),
                     headers=s.auth_headers())
        s.record("DELETE /friends/block/{id}/ (unblock)", ok_)
    else:
        skip("Block/unblock — could not create block target user")


# ════════════════════════════════════════════════════════════════════════════
# MESSAGING TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_messaging(s: State):
    hdr("MESSAGING")

    if not s.access or not s.user_b_id or not s.friendship_id:
        skip("Messaging — need auth + friendship first")
        return

    # ── Start conversation ────────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/conversations/start/"), headers=s.auth_headers(),
                 json_body={"user_id": s.user_b_id})
    if ok_ and r:
        s.conversation_id = r.json().get("data", {}).get("conversation", {}).get("id")
    s.record("POST /conversations/start/", ok_ and bool(s.conversation_id))

    # ── Conversations list ────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/conversations/"), headers=s.auth_headers())
    s.record("GET /conversations/", ok_)

    if not s.conversation_id:
        skip("Message tests — no conversation")
        return

    # ── Send message ──────────────────────────────────────────────────────────
    r, ok_ = req("POST", s.url(f"/api/v1/conversations/{s.conversation_id}/messages/"),
                 headers=s.auth_headers(),
                 json_body={"content": "Hello from live API test!"})
    if ok_ and r:
        s.message_id = r.json().get("data", {}).get("message", {}).get("id")
    s.record("POST /conversations/{id}/messages/", ok_ and bool(s.message_id))

    # ── Send second message for delete testing ────────────────────────────────
    r2, _ = req("POST", s.url(f"/api/v1/conversations/{s.conversation_id}/messages/"),
                headers=s.auth_headers(), json_body={"content": "Message to delete"})
    delete_msg_id = r2.json().get("data", {}).get("message", {}).get("id") if r2 else None

    # ── Get message history ───────────────────────────────────────────────────
    r, ok_ = req("GET", s.url(f"/api/v1/conversations/{s.conversation_id}/messages/"),
                 headers=s.auth_headers())
    passed = ok_ and len(r.json().get("data", {}).get("messages", [])) >= 1
    s.record("GET /conversations/{id}/messages/", passed)

    # ── Translate message ─────────────────────────────────────────────────────
    if s.message_id:
        r, ok_ = req("POST", s.url(f"/api/v1/conversations/messages/{s.message_id}/translate/"),
                     headers=s.auth_headers(), json_body={"language": "ar"})
        passed = ok_ and "translated_content" in r.json().get("data", {})
        s.record("POST /conversations/messages/{id}/translate/", passed)

    # ── Delete message for me ─────────────────────────────────────────────────
    if delete_msg_id:
        r, ok_ = req("DELETE", s.url(f"/api/v1/conversations/messages/{delete_msg_id}/"),
                     headers=s.auth_headers(), json_body={"scope": "me"})
        s.record("DELETE /conversations/messages/{id}/ (scope=me)", ok_)

    # ── Delete for everyone ───────────────────────────────────────────────────
    if s.message_id:
        r, ok_ = req("DELETE", s.url(f"/api/v1/conversations/messages/{s.message_id}/"),
                     headers=s.auth_headers(), json_body={"scope": "everyone"})
        s.record("DELETE /conversations/messages/{id}/ (scope=everyone)", ok_)

    # ── Unauthenticated access blocked ───────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/conversations/"), expected=401)
    s.record("GET /conversations/ (no auth → 401)", ok_)


# ════════════════════════════════════════════════════════════════════════════
# VOICE TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_voice(s: State):
    hdr("VOICE")

    if not s.access:
        skip("Voice — no access token")
        return

    # ── Get sentences ─────────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/voice/sentences/"), headers=s.auth_headers())
    if ok_ and r:
        sentences = r.json().get("data", {}).get("sentences", [])
        s.voice_sentence_ids = [sent.get("id") for sent in sentences]
    passed = ok_ and len(s.voice_sentence_ids) == 5
    s.record("GET /voice/sentences/ (5 sentences)", passed)
    if not passed:
        skip("Voice sentences not seeded — run: python manage.py load_voice_sentences")

    # ── Get voice status ──────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/voice/status/"), headers=s.auth_headers())
    passed = ok_ and "voice_trained" in r.json().get("data", {})
    s.record("GET /voice/status/", passed)

    # ── Upload voice sample (synthetic WAV) ───────────────────────────────────
    import io, wave, struct, math

    def make_wav(duration=4.0, sr=16000):
        n = int(duration * sr)
        samples = [int(8000 * math.sin(2 * math.pi * 440 * i / sr)) for i in range(n)]
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
            wf.writeframes(struct.pack(f"<{n}h", *samples))
        buf.seek(0)
        return buf

    upload_passed = 0
    for idx in range(1, 4):   # upload 3 samples
        wav_buf = make_wav()
        sentence_id = s.voice_sentence_ids[idx - 1] if s.voice_sentence_ids else None
        form_data = {"sample_index": str(idx)}
        if sentence_id:
            form_data["sentence_id"] = sentence_id
        files = {"audio_file": (f"sample_{idx}.wav", wav_buf, "audio/wav")}
        r, ok_ = req("POST", s.url("/api/v1/voice/samples/"),
                     headers=s.auth_headers(), files=files, data=form_data)
        if ok_:
            upload_passed += 1
    s.record(f"POST /voice/samples/ (uploaded {upload_passed}/3)", upload_passed > 0)

    # ── Delete a sample (re-record) ───────────────────────────────────────────
    r, ok_ = req("DELETE", s.url("/api/v1/voice/samples/1/"), headers=s.auth_headers())
    s.record("DELETE /voice/samples/1/ (re-record)", ok_)

    # ── Train without all 5 samples → 400 ────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/voice/train/"), headers=s.auth_headers(),
                 expected=400)
    s.record("POST /voice/train/ (insufficient samples → 400)", ok_)

    # ── Reset voice profile ───────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/voice/reset/"), headers=s.auth_headers())
    s.record("POST /voice/reset/", ok_)


# ════════════════════════════════════════════════════════════════════════════
# CALLS TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_calls(s: State):
    hdr("CALLS")

    if not s.access or not s.user_b_id or not s.friendship_id:
        skip("Calls — need auth + friendship first")
        return

    # ── No active call initially ──────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/calls/active/"), headers=s.auth_headers())
    passed = ok_ and r.json().get("data", {}).get("active_call") is None
    s.record("GET /calls/active/ (none initially)", passed)

    # ── Initiate call ─────────────────────────────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/calls/initiate/"), headers=s.auth_headers(),
                 json_body={"callee_id": s.user_b_id})
    if ok_ and r:
        data = r.json().get("data", {})
        s.call_room_id = data.get("room", {}).get("room_id")
    s.record("POST /calls/initiate/", ok_ and bool(s.call_room_id))

    if not s.call_room_id:
        skip("Remaining call tests — no room_id")
        return

    # ── ICE config ────────────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url(f"/api/v1/calls/ice-config/{s.call_room_id}/"),
                 headers=s.auth_headers())
    passed = ok_ and len(r.json().get("data", {}).get("ice_servers", [])) == 4
    s.record("GET /calls/ice-config/{room_id}/ (4 ICE servers)", passed)

    # ── Active call visible ───────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/calls/active/"), headers=s.auth_headers())
    passed = ok_ and r.json().get("data", {}).get("active_call") is not None
    s.record("GET /calls/active/ (call visible)", passed)

    # ── End call ──────────────────────────────────────────────────────────────
    r, ok_ = req("POST", s.url(f"/api/v1/calls/{s.call_room_id}/end/"),
                 headers=s.auth_headers())
    s.record("POST /calls/{room_id}/end/", ok_)

    # ── End already-ended call → 400 ─────────────────────────────────────────
    r, ok_ = req("POST", s.url(f"/api/v1/calls/{s.call_room_id}/end/"),
                 headers=s.auth_headers(), expected=400)
    s.record("POST /calls/{room_id}/end/ (already ended → 400)", ok_)

    # ── Initiate second call to test decline ──────────────────────────────────
    r, ok_ = req("POST", s.url("/api/v1/calls/initiate/"), headers=s.auth_headers(),
                 json_body={"callee_id": s.user_b_id})
    room2 = r.json().get("data", {}).get("room", {}).get("room_id") if ok_ and r else None

    if room2:
        # Decline as user B
        r, ok_ = req("POST", s.url(f"/api/v1/calls/{room2}/decline/"),
                     headers=s.auth_headers(s.user_b_access))
        s.record("POST /calls/{room_id}/decline/ (as callee)", ok_)

    # ── Call history ──────────────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/calls/history/"), headers=s.auth_headers())
    passed = ok_ and r.json().get("data", {}).get("total", 0) >= 1
    s.record("GET /calls/history/", passed)

    # ── Call history filter ───────────────────────────────────────────────────
    r, ok_ = req("GET", s.url("/api/v1/calls/history/?filter=outgoing"), headers=s.auth_headers())
    s.record("GET /calls/history/?filter=outgoing", ok_)

    # ── Non-friend cannot call ────────────────────────────────────────────────
    ts = int(time.time())
    r_new, _ = req("POST", s.url("/api/v1/auth/signup/"), json_body={
        "full_name": "Stranger", "email": f"stranger_{ts}@yaap.test",
        "password": "StrangerPass1!", "password_confirm": "StrangerPass1!",
    })
    stranger_id = r_new.json().get("data", {}).get("user", {}).get("id") if r_new else None
    if stranger_id:
        r, ok_ = req("POST", s.url("/api/v1/calls/initiate/"), headers=s.auth_headers(),
                     json_body={"callee_id": stranger_id}, expected=400)
        s.record("POST /calls/initiate/ (non-friend → 400)", ok_)


# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════

def print_summary(s: State):
    total   = len(s.results)
    passed  = sum(1 for _, status, _ in s.results if status == "PASS")
    failed  = total - passed

    print(f"\n{BOLD}{'═' * 60}{NC}")
    print(f"{BOLD}  YAAP Live API Test Summary{NC}")
    print(f"{'═' * 60}")
    print(f"  Total:   {total}")
    print(f"  {GREEN}Passed:  {passed}{NC}")
    if failed:
        print(f"  {RED}Failed:  {failed}{NC}")
        print(f"\n{BOLD}Failed tests:{NC}")
        for name, status, note in s.results:
            if status == "FAIL":
                print(f"  {RED}✗{NC} {name}")
                if note:
                    print(f"    {DIM}{note}{NC}")
    print(f"{'═' * 60}\n")

    return failed == 0


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

MODULES = {
    "auth":      test_auth,
    "profile":   test_profile,
    "friends":   test_friends,
    "messaging": test_messaging,
    "voice":     test_voice,
    "calls":     test_calls,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YAAP Live API Test Runner")
    parser.add_argument("modules", nargs="*", help="Modules to test (default: all)",
                        choices=list(MODULES.keys()) + ["all"])
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"Base URL (default: {DEFAULT_BASE})")
    args = parser.parse_args()

    selected = args.modules if args.modules and "all" not in args.modules else list(MODULES.keys())

    print(f"\n{BOLD}{CYAN}YAAP Live API Test Runner{NC}")
    print(f"  Base URL : {args.base}")
    print(f"  Modules  : {', '.join(selected)}")

    # Check server is up
    try:
        r = requests.get(f"{args.base}/health/", timeout=5)
        if r.status_code != 200:
            print(f"\n{RED}[ERROR] Backend returned {r.status_code}. Is it running?{NC}")
            sys.exit(1)
        print(f"  {GREEN}Server is up ✓{NC}\n")
    except requests.exceptions.ConnectionError:
        print(f"\n{RED}[ERROR] Cannot reach {args.base}. Start the backend first:{NC}")
        print(f"  {YELLOW}./run.sh start{NC}\n")
        sys.exit(1)

    state = State(args.base)

    # Run in dependency order (auth must run first, friends before messaging/calls)
    order = ["auth", "profile", "friends", "messaging", "voice", "calls"]
    for mod in order:
        if mod in selected:
            try:
                MODULES[mod](state)
            except Exception as e:
                print(f"\n{RED}[ERROR] Module '{mod}' crashed: {e}{NC}")
                traceback.print_exc()

    success = print_summary(state)
    sys.exit(0 if success else 1)
