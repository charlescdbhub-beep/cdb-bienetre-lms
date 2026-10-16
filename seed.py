#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed.py — LMS Bien-Être (fork Rosémary v2)
Crée l'école par défaut + superadmin + élève démo + 3 formations de l'accompagnement
+ un pack « Système complet » + codes d'accès (formation & pack) + annonce de bienvenue.
Idempotent (login-first côté API, SQL idempotent côté base).

Usage : python3 seed.py   (serveur SUR 51840 si dispo, sinon seed SQL pur)
"""
import json
import os
import sqlite3
import urllib.request

import db
import seed_data

BASE = "http://localhost:51840"
JAR = "/tmp/bwlms_seed_admin.txt"
COOKIE_NAME = "bienetre_session"

# ------------------------------------------------------------------
# 1. École par défaut
# ------------------------------------------------------------------
conn = db.get_conn()
if not db.q1(conn, "SELECT id FROM schools WHERE slug='bienetre'"):
    db.ex(conn, "INSERT INTO schools (id, name, slug, accent, tagline, created_at) VALUES (?,?,?,?,?,?)",
          (db.new_id(), "CDB Bien-Être — Accompagnement", "bienetre", "sage",
           "Ressources & parcours des praticiens accompagnés", db.now()))
    print("École bienetre créée")
else:
    print("École bienetre déjà présente")
SCHOOL_ID = db.q1(conn, "SELECT id FROM schools WHERE slug='bienetre'")["id"]
conn.close()

# ------------------------------------------------------------------
# 2. Comptes (via API si serveur lancé ; sinon SQL direct)
# ------------------------------------------------------------------
def api(path, body=None, method=None, jar=JAR):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method or ("POST" if body is not None else "GET"))
    for k, v in headers.items():
        req.add_header(k, v)
    if os.path.exists(jar):
        req.add_header("Cookie", open(jar).read().strip())
    try:
        resp = urllib.request.urlopen(req, timeout=10)
    except Exception:
        return None
    setc = resp.headers.get_all("Set-Cookie") or []
    tokens = [c.split(";")[0] for c in setc if c.startswith(COOKIE_NAME + "=")]
    if tokens:
        with open(jar, "w") as f:
            f.write(tokens[0])
    raw = resp.read()
    return json.loads(raw) if raw else {}

def ensure_user_sql(email, pw, name, role, school_id):
    """Crée le compte DIRECTEMENT en SQL (bcrypt via auth) — indépendant du serveur."""
    import auth as _auth
    conn = db.get_conn()
    row = db.q1(conn, "SELECT id, role, school_id FROM users WHERE email=?", (email,))
    if row:
        if row["role"] != role or (school_id and row["school_id"] != school_id):
            db.ex(conn, "UPDATE users SET role=?, school_id=? WHERE id=?", (role, school_id or row["school_id"], row["id"]))
            print(f"  rôle corrigé pour {email} → {role}")
        uid = row["id"]
    else:
        uid = db.new_id()
        db.ex(conn, "INSERT INTO users (id, email, password_hash, name, role, school_id, created_at) VALUES (?,?,?,?,?,?,?)",
              (uid, email, _auth.hash_password(pw), name, role, school_id, db.now()))
        print(f"  + compte {email} ({role})")
    conn.close()
    return uid

print("== Comptes ==")
try:
    import auth  # bcrypt dispo ?
    ensure_user_sql("charles@cdb-hub.app", "Rosemary2026!", "Charles Doe Bruce", "superadmin", None)
    ensure_user_sql("demo@cdb-hub.app", "Demo2026!BienLms", "Praticien Démo", "student", SCHOOL_ID)
except Exception as e:
    print("  fallback API:", e)

# ------------------------------------------------------------------
# 3. Formations (idempotent par slug)
# ------------------------------------------------------------------
conn = db.get_conn()
print("\n== Formations ==")
for pos, cdef in enumerate(seed_data.ALL_COURSES):
    exists = db.q1(conn, "SELECT id FROM courses WHERE school_id=? AND slug=?", (SCHOOL_ID, cdef["slug"]))
    if exists:
        print(f"  {cdef['slug']} déjà présent")
        continue
    cid = db.new_id()
    db.ex(conn, """INSERT INTO courses
        (id, school_id, slug, title, subtitle, description_html, level, price, old_price,
         duration_hours, color_card, cover_url, status, position, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, SCHOOL_ID, cdef["slug"], cdef["title"], cdef["subtitle"], cdef["desc"],
         cdef["level"], cdef["price"], cdef["old_price"], cdef["duration"], cdef["color"],
         "", "published", pos, db.now()))
    q_count = 0
    for mpos, mdef in enumerate(cdef["modules"]):
        mid = db.new_id()
        db.ex(conn, "INSERT INTO modules (id, course_id, title, description, position) VALUES (?,?,?,?,?)",
              (mid, cid, mdef["title"], mdef["desc"], mpos))
        for lpos, ldef in enumerate(mdef["lessons"]):
            lid = db.new_id()
            db.ex(conn, """INSERT INTO lessons
                (id, module_id, course_id, title, content_html, video_url, position, free_preview, drip_days, min_seconds, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (lid, mid, cid, ldef["title"], ldef["html"],
                 "" , lpos, 1 if ldef["free"] else 0, 0, 0, db.now()))
        # quiz en fin de module (leçon finale)
        quiz_lid = db.q1(conn, "SELECT id FROM lessons WHERE module_id=? ORDER BY position DESC LIMIT 1", (mid,))["id"]
        qtitle = "Quiz — " + mdef["title"].split("—")[-1].strip()
        qid = db.new_id()
        db.ex(conn, "INSERT INTO quizzes (id, lesson_id, title, pass_score) VALUES (?,?,?,?)",
              (qid, quiz_lid, qtitle, 70))
        qset = [seed_data.QUIZ_M1_F1, seed_data.QUIZ_M2_F1] if cdef["slug"] == "kit-demarrage" else \
               [seed_data.QUIZ_M1_F2, seed_data.QUIZ_M2_F2] if cdef["slug"] == "remplir-son-agenda" else \
               [seed_data.QUIZ_M1_F3, seed_data.QUIZ_M2_F3]
        for qq, qdata in enumerate(qset[mpos % len(qset)]):
            db.ex(conn, "INSERT INTO quiz_questions (id, quiz_id, question, options, correct, explanation, position) VALUES (?,?,?,?,?,?,?)",
                  (db.new_id(), qid, qdata["question"], json.dumps(qdata["options"], ensure_ascii=False),
                   qdata["correct"], qdata["explanation"], qq))
            q_count += 1
    print(f"  + {cdef['slug']} ({len(cdef['modules'])} modules, {q_count} questions quiz)")

# ------------------------------------------------------------------
# 4. Pack « Système complet » = F1 + F2 + F3 (code unique)
# ------------------------------------------------------------------
print("\n== Pack ==")
if not db.q1(conn, "SELECT id FROM packs WHERE school_id=? AND slug='accompagnement-complet'", (SCHOOL_ID,)):
    pid = db.new_id()
    db.ex(conn, """INSERT INTO packs (id, school_id, slug, title, subtitle, description_html, price, old_price, color_card, position, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
          (pid, SCHOOL_ID, "accompagnement-complet",
           "Programme d'accompagnement complet", "F1 + F2 + F3 — tout le système, un seul accès",
           "<p>Toutes les formations de l'accompagnement, débloquées d'un coup avec ton code unique remis par ton coach.</p>",
           997, 1290, "#1BA098", 0, db.now()))
    for row in db.q(conn, "SELECT id FROM courses WHERE school_id=? ORDER BY position", (SCHOOL_ID,)):
        db.ex(conn, "INSERT OR IGNORE INTO pack_courses (pack_id, course_id) VALUES (?,?)", (pid, row["id"]))
    print("  + pack accompagnement-complet (3 formations)")
else:
    pid = db.q1(conn, "SELECT id FROM packs WHERE school_id=? AND slug='accompagnement-complet'", (SCHOOL_ID,))["id"]
    print("  pack déjà présent")

# ------------------------------------------------------------------
# 5. Codes d'accès démo + annonces
# ------------------------------------------------------------------
f1 = db.q1(conn, "SELECT id FROM courses WHERE school_id=? AND slug='kit-demarrage'", (SCHOOL_ID,))
f1_id = f1["id"] if f1 else None
if not db.q(conn, "SELECT id FROM access_codes WHERE school_id=?", (SCHOOL_ID,)):
    for code in ["BLW-BIEN-2026", "BLW-DEPART"]:
        db.ex(conn, "INSERT INTO access_codes (id, school_id, course_id, code, status, note, created_at) VALUES (?,?,?,?,?,?,?)",
              (db.new_id(), SCHOOL_ID, f1_id, code, "active", "code démo F1 — rechargeable", db.now()))
    # 1 code pack démo
    db.ex(conn, "INSERT INTO access_codes (id, school_id, course_id, pack_id, code, status, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
          (db.new_id(), SCHOOL_ID, None, pid, "BLW-PACK-FULL", "active", "code pack démo — débloque F1+F2+F3", db.now()))
    print("  codes démo : BLW-BIEN-2026, BLW-DEPART (F1) · BLW-PACK-FULL (pack complet)")
else:
    print("  codes déjà présents")

if not db.q(conn, "SELECT id FROM announcements WHERE school_id=?", (SCHOOL_ID,)):
    db.ex(conn, "INSERT INTO announcements (id, school_id, course_id, title, body, created_at) VALUES (?,?,?,?,?,?)",
          (db.new_id(), SCHOOL_ID, f1_id,
           "Bienvenue dans ton espace d'accompagnement 🌿",
           "Tes parcours sont ouverts. Chaque leçon se termine par une action de 15 minutes — et ton coach te répond directement sous chaque leçon (onglet Coach).",
           db.now()))
    print("  annonce de bienvenue créée")

conn.close()
print("\n✅ Seed terminé. Comptes : charles@cdb-hub.app / Rosemary2026! (superadmin) · demo@cdb-hub.app / Demo2026!BienLms (élève)")
print("   Codes : BLW-BIEN-2026 · BLW-DEPART (F1) · BLW-PACK-FULL (pack 3 formations)")