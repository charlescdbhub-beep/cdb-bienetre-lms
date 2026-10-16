#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rosémary — École de Numérologie · SaaS LMS multi-écoles
db.py — Schéma SQLite (WAL, une connexion par requête)
Pattern CDB HUB : tenant_id (school_id) sur TOUTES les tables métier.
"""
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "/workspace/cdb-bienetre-lms/data/bienetre.db"


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn(db_path: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def q1(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def ex(conn, sql, params=()):
    conn.execute(sql, params)
    conn.commit()


# ------------------------------------------------------------------
# Schéma
# ------------------------------------------------------------------
SCHEMA = """
-- Écoles = tenants. Un formateur = une école. Charles = superadmin au-dessus.
CREATE TABLE IF NOT EXISTS schools (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    slug             TEXT UNIQUE NOT NULL,
    accent           TEXT NOT NULL DEFAULT 'sage',      -- 'sage' | 'emerald' | 'mystic'
    tagline          TEXT DEFAULT '',
    landing_html     TEXT DEFAULT '',                   -- surcharge landing par école
    created_at       TEXT NOT NULL
);

-- Utilisateurs ; school_id NULL = superadmin (flotte CDB)
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name          TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'student',      -- 'student'|'school_admin'|'superadmin'
    school_id     TEXT REFERENCES schools(id),
    tags          TEXT DEFAULT '',                      -- tags libres séparés par des virgules
    created_at    TEXT NOT NULL
);

-- Sessions persistées (survivent aux restarts)
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- Formations
CREATE TABLE IF NOT EXISTS courses (
    id              TEXT PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id),
    slug            TEXT NOT NULL,
    title           TEXT NOT NULL,
    subtitle        TEXT DEFAULT '',
    description_html TEXT DEFAULT '',
    level           TEXT DEFAULT 'débutant',
    price           REAL DEFAULT 0,
    old_price       REAL,
    duration_hours  TEXT DEFAULT '',
    color_card      TEXT DEFAULT '',                   -- couleur de vignette (landing)
    cover_url       TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'draft',     -- 'draft'|'published'
    position        INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    UNIQUE(school_id, slug)
);

-- Modules
CREATE TABLE IF NOT EXISTS modules (
    id         TEXT PRIMARY KEY,
    course_id  TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    description TEXT DEFAULT '',
    position   INTEGER DEFAULT 0
);

-- Leçons
CREATE TABLE IF NOT EXISTS lessons (
    id           TEXT PRIMARY KEY,
    module_id    TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    course_id    TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    content_html TEXT DEFAULT '',
    video_url    TEXT DEFAULT '',
    pdf_name     TEXT DEFAULT '',
    pdf_data     BLOB,
    position   INTEGER DEFAULT 0,
    free_preview INTEGER DEFAULT 0,
    drip_days  INTEGER DEFAULT 0,
    drip_date  TEXT DEFAULT '',                      -- libération à une DATE précise (ISO) — Teachizy
    min_seconds INTEGER DEFAULT 0,                   -- temps de visionnage actif requis (Qualiopi)
    created_at TEXT NOT NULL
);

-- Temps de visionnage actif (l'élève envoie un tick toutes les 15 s SEULEMENT si onglet visible)
CREATE TABLE IF NOT EXISTS lesson_time (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    lesson_id  TEXT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    course_id  TEXT NOT NULL,
    seconds    INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, lesson_id)
);

-- Commentaires privés datés : fil élève ↔ coach PAR LEÇON
CREATE TABLE IF NOT EXISTS lesson_comments (
    id          TEXT PRIMARY KEY,
    lesson_id   TEXT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL REFERENCES users(id),     -- propriétaire du fil (l'élève)
    author_id   TEXT NOT NULL,
    author_role TEXT NOT NULL DEFAULT 'student',        -- 'student' | 'coach'
    body        TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

-- Satisfaction à chaud (à 100 % de complétion)
CREATE TABLE IF NOT EXISTS feedback (
    id         TEXT PRIMARY KEY,
    school_id  TEXT NOT NULL,
    course_id  TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    rating     INTEGER NOT NULL DEFAULT 5,
    comment    TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, course_id)
);

-- Quiz attachés à une leçon (généralement la dernière d'un module)
CREATE TABLE IF NOT EXISTS quizzes (
    id         TEXT PRIMARY KEY,
    lesson_id  TEXT UNIQUE REFERENCES lessons(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    pass_score INTEGER NOT NULL DEFAULT 70               -- % requis
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id          TEXT PRIMARY KEY,
    quiz_id     TEXT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    options     TEXT NOT NULL,       -- JSON array
    correct     INTEGER NOT NULL DEFAULT 0,
    explanation TEXT DEFAULT '',
    position    INTEGER DEFAULT 0
);

-- Inscriptions
CREATE TABLE IF NOT EXISTS enrollments (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    course_id   TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    school_id   TEXT NOT NULL,
    source      TEXT DEFAULT 'code',                   -- 'code'|'manual'
    code        TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'active',        -- 'active'|'completed'
    enrolled_at TEXT NOT NULL,
    UNIQUE(user_id, course_id)
);

-- Packs = bundle de formations rachetable par 1 seul code (inspiration Teachizy)
CREATE TABLE IF NOT EXISTS packs (
    id         TEXT PRIMARY KEY,
    school_id  TEXT NOT NULL REFERENCES schools(id),
    slug       TEXT NOT NULL,
    title      TEXT NOT NULL,
    subtitle   TEXT DEFAULT '',
    description_html TEXT DEFAULT '',
    price      REAL DEFAULT 0,
    old_price  REAL,
    color_card TEXT DEFAULT '',
    position   INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(school_id, slug)
);

CREATE TABLE IF NOT EXISTS pack_courses (
    pack_id   TEXT NOT NULL REFERENCES packs(id) ON DELETE CASCADE,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE(pack_id, course_id)
);

-- Codes d'accès premium
CREATE TABLE IF NOT EXISTS access_codes (
    id         TEXT PRIMARY KEY,
    school_id  TEXT NOT NULL REFERENCES schools(id),
    course_id  TEXT REFERENCES courses(id),              -- NULL si le code cible un pack
    pack_id    TEXT REFERENCES packs(id),
    code       TEXT UNIQUE NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active',           -- 'active'|'used'|'revoked'
    used_by    TEXT,
    used_at    TEXT,
    note       TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- Progression (une ligne par couple user/leçon)
CREATE TABLE IF NOT EXISTS progress (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    lesson_id    TEXT NOT NULL REFERENCES lessons(id),
    course_id    TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    UNIQUE(user_id, lesson_id)
);

-- Tentatives de quiz
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    quiz_id     TEXT NOT NULL,
    score       REAL NOT NULL,
    max_score   REAL NOT NULL,
    passed      INTEGER NOT NULL DEFAULT 0,
    answers     TEXT DEFAULT '[]',
    taken_at    TEXT NOT NULL
);

-- Certificats
CREATE TABLE IF NOT EXISTS certificates (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    course_id    TEXT NOT NULL,
    serial       TEXT UNIQUE NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'reussite',      -- 'reussite' | 'assiduite'
    student_name TEXT NOT NULL,
    course_title TEXT NOT NULL,
    issued_at    TEXT NOT NULL
);

-- Annonces (par école, éventuellement ciblées sur un cours)
CREATE TABLE IF NOT EXISTS announcements (
    id         TEXT PRIMARY KEY,
    school_id  TEXT NOT NULL,
    course_id  TEXT,
    title      TEXT NOT NULL,
    body       TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- Leads de la landing publique (captation visiteurs)
CREATE TABLE IF NOT EXISTS leads (
    id         TEXT PRIMARY KEY,
    school_id  TEXT,
    name       TEXT DEFAULT '',
    email      TEXT NOT NULL,
    goal       TEXT DEFAULT '',
    source     TEXT DEFAULT 'landing',
    status     TEXT NOT NULL DEFAULT 'nouveau',
    created_at TEXT NOT NULL,
    UNIQUE(school_id, email)
);

-- Réglages clé/valeur par école
CREATE TABLE IF NOT EXISTS settings (
    id        TEXT PRIMARY KEY,
    school_id TEXT NOT NULL,
    key       TEXT NOT NULL,
    value     TEXT DEFAULT '',
    UNIQUE(school_id, key)
);

CREATE INDEX IF NOT EXISTS idx_courses_school  ON courses(school_id, status, position);
CREATE INDEX IF NOT EXISTS idx_modules_course  ON modules(course_id, position);
CREATE INDEX IF NOT EXISTS idx_lessons_module  ON lessons(module_id, position);
CREATE INDEX IF NOT EXISTS idx_enroll_user     ON enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_user   ON progress(user_id, course_id);
CREATE INDEX IF NOT EXISTS idx_comments_lesson ON lesson_comments(lesson_id, user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_time_user       ON lesson_time(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_course ON feedback(course_id);
"""


def init_db(db_path: str = None) -> str:
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    tables = [r[0] for r in q(conn, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    conn.close()
    return ", ".join(tables)


if __name__ == "__main__":
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    print("DB init:", DB_PATH)
    print("Tables:", init_db())