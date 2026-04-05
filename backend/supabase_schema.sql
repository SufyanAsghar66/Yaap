-- ═══════════════════════════════════════════════════════════════════════════
-- YAAP — Supabase PostgreSQL Schema
-- Run this in the Supabase SQL editor (Dashboard → SQL Editor → New Query)
-- Order matters: run sections top to bottom.
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- for fuzzy name search
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Enums ───────────────────────────────────────────────────────────────────
CREATE TYPE auth_provider_enum AS ENUM (
    'email_password', 'email_otp', 'google'
);

CREATE TYPE last_seen_visibility_enum AS ENUM (
    'everyone', 'friends', 'nobody'
);

CREATE TYPE friend_request_status_enum AS ENUM (
    'pending', 'accepted', 'declined', 'cancelled'
);

CREATE TYPE message_status_enum AS ENUM (
    'sent', 'delivered', 'read'
);

CREATE TYPE call_status_enum AS ENUM (
    'initiated', 'answered', 'missed', 'declined', 'ended'
);

CREATE TYPE voice_job_status_enum AS ENUM (
    'pending', 'processing', 'completed', 'failed'
);

-- ═══════════════════════════════════════════════════════════════════════════
-- TABLES
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                   TEXT UNIQUE NOT NULL,
    full_name               TEXT NOT NULL,
    display_name            TEXT NOT NULL DEFAULT '',
    supabase_uid            TEXT UNIQUE,
    avatar_url              TEXT NOT NULL DEFAULT '',
    bio                     TEXT NOT NULL DEFAULT '' CHECK (char_length(bio) <= 160),
    date_of_birth           DATE,
    country_code            CHAR(2) NOT NULL DEFAULT '',
    timezone                TEXT NOT NULL DEFAULT 'UTC',
    language_preference     TEXT NOT NULL DEFAULT 'en',
    voice_trained           BOOLEAN NOT NULL DEFAULT FALSE,
    voice_embedding         JSONB,
    auth_provider           auth_provider_enum NOT NULL DEFAULT 'email_password',
    profile_complete        BOOLEAN NOT NULL DEFAULT FALSE,
    language_selected       BOOLEAN NOT NULL DEFAULT FALSE,
    is_online               BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen               TIMESTAMPTZ,
    last_seen_visibility    last_seen_visibility_enum NOT NULL DEFAULT 'everyone',
    show_read_receipts      BOOLEAN NOT NULL DEFAULT TRUE,
    show_online_status      BOOLEAN NOT NULL DEFAULT TRUE,
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Email OTPs ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_otps (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT NOT NULL,
    code        CHAR(6) NOT NULL,
    is_used     BOOLEAN NOT NULL DEFAULT FALSE,
    attempts    SMALLINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

-- ─── Friend Requests ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS friend_requests (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status       friend_request_status_enum NOT NULL DEFAULT 'pending',
    message      TEXT NOT NULL DEFAULT '' CHECK (char_length(message) <= 200),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    CONSTRAINT no_self_request CHECK (from_user_id <> to_user_id)
);

-- ─── Friendships ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS friendships (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_b_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_a_id, user_b_id),
    CONSTRAINT ordered_pair CHECK (user_a_id < user_b_id)
);

-- ─── Blocks ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS blocks (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blocker_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (blocker_id, blocked_id),
    CONSTRAINT no_self_block CHECK (blocker_id <> blocked_id)
);

-- ─── User Devices (FCM) ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_devices (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fcm_token    TEXT UNIQUE NOT NULL,
    device_name  TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Conversations ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_a_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    participant_b_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_message_id   UUID,   -- FK added after messages table
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participant_a_id, participant_b_id),
    CONSTRAINT ordered_participants CHECK (participant_a_id < participant_b_id)
);

-- ─── Messages ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id       UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content               TEXT NOT NULL,
    original_language     TEXT NOT NULL DEFAULT 'en',
    status                message_status_enum NOT NULL DEFAULT 'sent',
    deleted_for_everyone  BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at            TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add FK now that messages table exists
ALTER TABLE conversations
    ADD CONSTRAINT fk_last_message
    FOREIGN KEY (last_message_id)
    REFERENCES messages(id)
    ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

-- ─── Message Deletions (delete for me) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS message_deletions (
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    deleted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (message_id, user_id)
);

-- ─── Message Translations ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS message_translations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    language            TEXT NOT NULL,
    translated_content  TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (message_id, language)
);

-- ─── Voice Samples ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS voice_samples (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sample_index     SMALLINT NOT NULL CHECK (sample_index BETWEEN 1 AND 5),
    storage_path     TEXT NOT NULL,
    duration_seconds FLOAT,
    uploaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, sample_index)
);

-- ─── Voice Training Jobs ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS voice_training_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status       voice_job_status_enum NOT NULL DEFAULT 'pending',
    celery_task_id TEXT,
    error_message TEXT,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Voice Training Sentences ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS voice_sentences (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    language  TEXT NOT NULL,
    sentence  TEXT NOT NULL,
    position  SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 5),
    UNIQUE (language, position)
);

-- ─── Call Records ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS call_records (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    callee_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    room_id          UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    status           call_status_enum NOT NULL DEFAULT 'initiated',
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    answered_at      TIMESTAMPTZ,
    ended_at         TIMESTAMPTZ,
    duration_seconds INT,
    CONSTRAINT no_self_call CHECK (caller_id <> callee_id)
);

-- ═══════════════════════════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════════════════════════

-- Users
CREATE INDEX idx_users_email              ON users(email);
CREATE INDEX idx_users_display_name       ON users USING gin(display_name gin_trgm_ops);
CREATE INDEX idx_users_full_name          ON users USING gin(full_name gin_trgm_ops);
CREATE INDEX idx_users_supabase_uid       ON users(supabase_uid);
CREATE INDEX idx_users_is_online          ON users(is_online) WHERE is_online = TRUE;
CREATE INDEX idx_users_country            ON users(country_code);

-- OTPs
CREATE INDEX idx_email_otps_lookup        ON email_otps(email, is_used, expires_at);

-- Friend Requests
CREATE INDEX idx_freq_to_user_pending     ON friend_requests(to_user_id, status) WHERE status = 'pending';
CREATE INDEX idx_freq_from_user_pending   ON friend_requests(from_user_id, status) WHERE status = 'pending';
CREATE INDEX idx_freq_responded_at        ON friend_requests(from_user_id, responded_at) WHERE status = 'declined';

-- Friendships
CREATE INDEX idx_friendships_user_a       ON friendships(user_a_id);
CREATE INDEX idx_friendships_user_b       ON friendships(user_b_id);

-- Conversations
CREATE INDEX idx_conv_participant_a       ON conversations(participant_a_id);
CREATE INDEX idx_conv_participant_b       ON conversations(participant_b_id);
CREATE INDEX idx_conv_updated            ON conversations(updated_at DESC);

-- Messages
CREATE INDEX idx_messages_conversation   ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_sender         ON messages(sender_id);
CREATE INDEX idx_messages_not_deleted    ON messages(conversation_id) WHERE deleted_for_everyone = FALSE;

-- Message Translations
CREATE INDEX idx_translations_msg_lang   ON message_translations(message_id, language);

-- Voice
CREATE INDEX idx_voice_samples_user      ON voice_samples(user_id);
CREATE INDEX idx_voice_jobs_user         ON voice_training_jobs(user_id, status);

-- Calls
CREATE INDEX idx_calls_caller            ON call_records(caller_id, started_at DESC);
CREATE INDEX idx_calls_callee            ON call_records(callee_id, started_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════
-- TRIGGERS (auto-update updated_at)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_messages_updated_at
    BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-update conversation.updated_at when a new message is inserted
CREATE OR REPLACE FUNCTION update_conversation_on_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET updated_at      = NOW(),
        last_message_id = NEW.id
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_message_updates_conversation
    AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION update_conversation_on_message();

-- ═══════════════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)
-- ═══════════════════════════════════════════════════════════════════════════
-- Django uses the SERVICE ROLE key which bypasses RLS.
-- RLS protects against direct Supabase client access from mobile apps.

ALTER TABLE users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_otps           ENABLE ROW LEVEL SECURITY;
ALTER TABLE friend_requests      ENABLE ROW LEVEL SECURITY;
ALTER TABLE friendships          ENABLE ROW LEVEL SECURITY;
ALTER TABLE blocks               ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_devices         ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages             ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_deletions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_translations ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_samples        ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_training_jobs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_records         ENABLE ROW LEVEL SECURITY;

-- Helper: get the YAAP user id matching the Supabase JWT sub claim
CREATE OR REPLACE FUNCTION current_yaap_user_id()
RETURNS UUID AS $$
    SELECT id FROM users WHERE supabase_uid = auth.uid()::TEXT LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ── Users ─────────────────────────────────────────────────────────────────────
-- Users can read their own full profile; others see only non-private fields via views
CREATE POLICY "users: own full access"
    ON users FOR ALL
    USING (id = current_yaap_user_id());

CREATE POLICY "users: public read active"
    ON users FOR SELECT
    USING (is_active = TRUE);

-- ── Email OTPs ────────────────────────────────────────────────────────────────
-- Only the service role (Django) touches OTPs; block all direct client access
CREATE POLICY "email_otps: service role only"
    ON email_otps FOR ALL
    USING (FALSE);   -- deny all; Django uses service role key which bypasses RLS

-- ── Friend Requests ───────────────────────────────────────────────────────────
CREATE POLICY "friend_requests: parties can read"
    ON friend_requests FOR SELECT
    USING (
        from_user_id = current_yaap_user_id() OR
        to_user_id   = current_yaap_user_id()
    );

CREATE POLICY "friend_requests: sender can insert"
    ON friend_requests FOR INSERT
    WITH CHECK (from_user_id = current_yaap_user_id());

CREATE POLICY "friend_requests: parties can update"
    ON friend_requests FOR UPDATE
    USING (
        from_user_id = current_yaap_user_id() OR
        to_user_id   = current_yaap_user_id()
    );

-- ── Friendships ───────────────────────────────────────────────────────────────
CREATE POLICY "friendships: participants can read"
    ON friendships FOR SELECT
    USING (
        user_a_id = current_yaap_user_id() OR
        user_b_id = current_yaap_user_id()
    );

-- ── Blocks ───────────────────────────────────────────────────────────────────
CREATE POLICY "blocks: blocker can manage"
    ON blocks FOR ALL
    USING (blocker_id = current_yaap_user_id());

-- ── User Devices ─────────────────────────────────────────────────────────────
CREATE POLICY "user_devices: owner can manage"
    ON user_devices FOR ALL
    USING (user_id = current_yaap_user_id());

-- ── Conversations ─────────────────────────────────────────────────────────────
CREATE POLICY "conversations: participants can read"
    ON conversations FOR SELECT
    USING (
        participant_a_id = current_yaap_user_id() OR
        participant_b_id = current_yaap_user_id()
    );

-- ── Messages ──────────────────────────────────────────────────────────────────
CREATE POLICY "messages: conversation participants can read"
    ON messages FOR SELECT
    USING (
        conversation_id IN (
            SELECT id FROM conversations
            WHERE participant_a_id = current_yaap_user_id()
               OR participant_b_id = current_yaap_user_id()
        )
        AND
        -- Exclude messages deleted for this user
        id NOT IN (
            SELECT message_id FROM message_deletions
            WHERE user_id = current_yaap_user_id()
        )
    );

CREATE POLICY "messages: sender can insert"
    ON messages FOR INSERT
    WITH CHECK (sender_id = current_yaap_user_id());

-- ── Message Deletions ─────────────────────────────────────────────────────────
CREATE POLICY "message_deletions: own records"
    ON message_deletions FOR ALL
    USING (user_id = current_yaap_user_id());

-- ── Message Translations ──────────────────────────────────────────────────────
CREATE POLICY "message_translations: conversation participants can read"
    ON message_translations FOR SELECT
    USING (
        message_id IN (
            SELECT m.id FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.participant_a_id = current_yaap_user_id()
               OR c.participant_b_id = current_yaap_user_id()
        )
    );

-- ── Voice ─────────────────────────────────────────────────────────────────────
CREATE POLICY "voice_samples: owner only"
    ON voice_samples FOR ALL
    USING (user_id = current_yaap_user_id());

CREATE POLICY "voice_training_jobs: owner only"
    ON voice_training_jobs FOR SELECT
    USING (user_id = current_yaap_user_id());

-- ── Call Records ──────────────────────────────────────────────────────────────
CREATE POLICY "call_records: participants can read"
    ON call_records FOR SELECT
    USING (
        caller_id = current_yaap_user_id() OR
        callee_id = current_yaap_user_id()
    );

-- ═══════════════════════════════════════════════════════════════════════════
-- SEED DATA — Voice Training Sentences
-- 5 sentences per language for the voice training activity
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO voice_sentences (language, position, sentence) VALUES
-- English
('en', 1, 'The quick brown fox jumps over the lazy dog near the riverbank.'),
('en', 2, 'She sells seashells by the seashore every morning before sunrise.'),
('en', 3, 'Technology is changing the way we communicate across the world.'),
('en', 4, 'The weather today is perfect for a long walk in the park.'),
('en', 5, 'I enjoy reading books and listening to music in my free time.'),
-- Arabic
('ar', 1, 'الثعلب البني السريع يقفز فوق الكلب الكسول بالقرب من النهر.'),
('ar', 2, 'التكنولوجيا تغير طريقة تواصلنا مع بعضنا البعض حول العالم.'),
('ar', 3, 'أستمتع بقراءة الكتب والاستماع إلى الموسيقى في وقت الفراغ.'),
('ar', 4, 'الطقس اليوم رائع للتنزه في الحديقة.'),
('ar', 5, 'أتعلم لغات جديدة لأتواصل مع أشخاص من ثقافات مختلفة.'),
-- Spanish
('es', 1, 'El veloz zorro marrón salta sobre el perro perezoso junto al río.'),
('es', 2, 'La tecnología está cambiando la forma en que nos comunicamos.'),
('es', 3, 'Me gusta leer libros y escuchar música en mi tiempo libre.'),
('es', 4, 'El tiempo hoy es perfecto para dar un largo paseo por el parque.'),
('es', 5, 'Aprendo idiomas para comunicarme con personas de diferentes culturas.'),
-- French
('fr', 1, 'Le rapide renard brun saute par-dessus le chien paresseux.'),
('fr', 2, 'La technologie change notre façon de communiquer dans le monde entier.'),
('fr', 3, 'J''aime lire des livres et écouter de la musique pendant mon temps libre.'),
('fr', 4, 'Le temps aujourd''hui est parfait pour une longue promenade dans le parc.'),
('fr', 5, 'J''apprends de nouvelles langues pour communiquer avec des personnes de cultures différentes.'),
-- German
('de', 1, 'Der schnelle braune Fuchs springt über den faulen Hund am Flussufer.'),
('de', 2, 'Technologie verändert die Art und Weise, wie wir miteinander kommunizieren.'),
('de', 3, 'Ich lese gerne Bücher und höre Musik in meiner Freizeit.'),
('de', 4, 'Das Wetter heute ist perfekt für einen langen Spaziergang im Park.'),
('de', 5, 'Ich lerne neue Sprachen, um mit Menschen aus verschiedenen Kulturen zu kommunizieren.')
ON CONFLICT (language, position) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- STORAGE BUCKETS (run via Supabase dashboard or API)
-- ═══════════════════════════════════════════════════════════════════════════
-- These cannot be created via SQL — run via the Supabase client or dashboard:
--
-- supabase.storage.createBucket('avatars',       { public: true  })
-- supabase.storage.createBucket('voice-samples', { public: false })  -- private!
--
-- Voice samples must be private — accessed only via signed URLs from Django.
