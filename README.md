# YAAP -- Real-Time Communication App

YAAP is a real-time communication app with a **Django backend** and a
**Kotlin Android frontend**, focused on messaging, voice calling, and
AI-powered language features.

------------------------------------------------------------------------

# 📁 Repository Structure

    Yaap/
    ├── backend/   → Django backend
    └── frontend/  → Kotlin Android app

------------------------------------------------------------------------

# ⚙️ Backend Setup & Run Guide

## 1️⃣ Go to backend folder

    cd backend

------------------------------------------------------------------------

## 2️⃣ Create & Activate Virtual Environment

### Windows PowerShell

    python -m venv .venv
    .venv\Scripts\Activate.ps1

### Windows CMD

    python -m venv .venv
    .venv\Scripts\activate.bat

------------------------------------------------------------------------

## 3️⃣ Install Dependencies

    pip install -r requirements.txt

------------------------------------------------------------------------

## 4️⃣ Start Redis (Docker Required)

Make sure **Docker Desktop is running**.

Run Redis container:

    docker run -d --name yaap_redis -p 6379:6379 redis:7-alpine

If container already exists:

    docker start yaap_redis

------------------------------------------------------------------------

## 5️⃣ Run Database Migrations

    python manage.py migrate

------------------------------------------------------------------------

## 6️⃣ Start Celery Worker

Open a **new terminal** in backend folder:

    celery -A yaap worker --loglevel=info --queues=default,email,voice_training,translation

------------------------------------------------------------------------

## 7️⃣ Start Daphne Server (ASGI)

Open another terminal:

    daphne -b 0.0.0.0 -p 8000 yaap.asgi:application

------------------------------------------------------------------------

## 8️⃣ Start Django Development Server

Open another terminal:

    python manage.py runserver

------------------------------------------------------------------------

# ▶️ Running Summary

You typically need **these services running simultaneously**:

  -------------------------------------------------------------------------------------------------------------------------------
  Service                             Command
  ----------------------------------- -------------------------------------------------------------------------------------------
  Redis                               `docker run -d --name yaap_redis -p 6379:6379 redis:7-alpine`

  Celery                              `celery -A yaap worker --loglevel=info --queues=default,email,voice_training,translation`

  Daphne                              `daphne -b 0.0.0.0 -p 8000 yaap.asgi:application`

  Django                              `python manage.py runserver`
  -------------------------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 🗄️ Supabase Session Pooling Fix

If you encounter **Supabase session pooling errors**, update:

    Yaap/backend/yaap/settings.py

### Change this:

``` python
# DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_MAX_AGE"] = 0
```

This disables persistent DB connections and works correctly with
connection pooling.

------------------------------------------------------------------------

# ✅ Backend is Ready

Your backend should now be running successfully 🚀
