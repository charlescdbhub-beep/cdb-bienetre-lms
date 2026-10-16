#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CDB Studio Bien-Être · LMS d'accompagnement (fork Rosémary LMS v1.0)
server.py — HTTP stdlib BaseHTTPRequestHandler, pattern CDB HUB.
Port 51840. Multi-écoles : chaque praticien accompagné = une école.
Ajouts Teachizy-inspired : packs, commentaires coach↔élève, satisfaction à chaud,
temps de visionnage actif (pause hors onglet côté front), attestations d'assiduité,
drip par date précise, tags élèves.
"""
import base64
import json
import mimetypes
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import db
import auth

PORT = int(os.environ.get("BIENETRE_LMS_PORT", "51840"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DEFAULT_SCHOOL_SLUG = os.environ.get("BIENETRE_LMS_SCHOOL", "bienetre")
VERSION = "2.0.0"


# ==================================================================
# Helpers réponses (pattern CDB)
# ==================================================================
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ---- basics -------------------------------------------------
    def log_message(self, fmt, *args):
        pass  # silence logs

    def _send(self, code, body: bytes, ctype: str, extra=None, cors_origin=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cors_origin is not None:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200, cookies=None, cors_origin=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        extra = []
        for c in (cookies or []):
            extra.append(("Set-Cookie", c))
        self._send(code, body, "application/json; charset=utf-8", extra, cors_origin)

    def _html(self, html: str, code=200, cookies=None):
        body = html.encode("utf-8")
        extra = []
        for c in (cookies or []):
            extra.append(("Set-Cookie", c))
        self._send(code, body, "text/html; charset=utf-8", extra)

    def _cookie(self, token: str) -> str:
        return f"{auth.COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={14*86400}"

    def _clear_cookie(self) -> str:
        return f"{auth.COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    def _get_cookie_token(self) -> str:
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            part = part.strip()
            if part.startswith(auth.COOKIE + "="):
                return part[len(auth.COOKIE) + 1:]
        return ""

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # CORS preflight (public endpoints)
    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        self._send(204, b"", "text/plain", cors_origin=origin)

    # ---- http verbs ---------------------------------------------
    def do_GET(self):
        self.route("GET")
    def do_POST(self):
        self.route("POST")
    def do_PATCH(self):
        self.route("PATCH")
    def do_PUT(self):
        self.route("PUT")
    def do_DELETE(self):
        self.route("DELETE")

    # ---- routing ------------------------------------------------
    def route(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health
        if path == "/api/health":
            return self._json({"ok": True, "app": "bienetre-lms", "version": VERSION})

        # Static assets (avant toute auth — piège n°19)
        if method == "GET" and path.startswith("/static/"):
            filename = os.path.basename(path[len("/static/"):])
            return self._static(filename)
        if method == "GET" and path.startswith("/assets/"):
            filename = os.path.basename(path[len("/assets/"):])
            return self._static(filename, sub="assets")

        # PDF d'une leçon
        m = re.match(r"^/pdf/([a-f0-9]+)$", path)
        if method == "GET" and m:
            return self._serve_pdf(m.group(1))

        conn = db.get_conn()

        try:
            user = auth.user_from_token(conn, self._get_cookie_token())

            # ---------- PAGES ----------
            if method == "GET" and path == "/":
                return self._page_landing(conn, user)
            if method == "GET" and path == "/login":
                if user:
                    return self._redirect("/app")
                return self._page_login()
            if method == "GET" and path == "/signup":
                return self._page_login(mode="signup")
            if method == "GET" and path == "/app":
                if not user:
                    return self._redirect("/login")
                return self._page_app(conn, user)
            if method == "GET" and path == "/logout":
                auth.destroy_session(conn, self._get_cookie_token())
                return self._redirect("/")

            # Page formation publique
            m = re.match(r"^/formation/([a-z0-9-]+)$", path)
            if method == "GET" and m:
                return self._page_course(conn, user, m.group(1))

            # ---------- API publique ----------
            if method == "GET" and path == "/api/public/courses":
                return self._api_public_courses(conn)
            if path.startswith("/api/public/"):
                return self._api_public(conn, method, path)

            # ---------- API auth ----------
            if path == "/api/auth/signup" and method == "POST":
                return self._api_signup(conn)
            if path == "/api/auth/login" and method == "POST":
                return self._api_login(conn)
            if path == "/api/auth/logout" and method == "POST":
                auth.destroy_session(conn, self._get_cookie_token())
                return self._json({"ok": True}, cookies=[self._clear_cookie()])

            # tout le reste exige une session
            if not user:
                return self._json({"error": "unauthorized"}, code=401)

            # étudiant
            if path == "/api/me" and method == "GET":
                return self._api_me(conn, user)
            if path == "/api/redeem" and method == "POST":
                return self._api_redeem(conn, user)
            if path == "/api/my/courses" and method == "GET":
                return self._api_my_courses(conn, user)
            m = re.match(r"^/api/my/course/([a-f0-9]+)$", path)
            if method == "GET" and m:
                return self._api_my_course(conn, user, m.group(1))
            m = re.match(r"^/api/lesson/([a-f0-9]+)$", path)
            if method == "GET" and m:
                return self._api_lesson(conn, user, m.group(1))
            if path == "/api/progress" and method == "POST":
                return self._api_progress(conn, user)
            m = re.match(r"^/api/my/quiz/([a-f0-9]+)$", path)
            if method == "GET" and m:
                return self._api_quiz(conn, user, m.group(1))
            m = re.match(r"^/api/quiz/([a-f0-9]+)/attempt$", path)
            if method == "POST" and m:
                return self._api_quiz_attempt(conn, user, m.group(1))
            # ----- v2 : temps de visionnage actif (tick 15 s, onglet visible) -----
            if path == "/api/lesson/time" and method == "POST":
                return self._api_lesson_time(conn, user)
            # ----- v2 : commentaires coach↔élève par leçon -----
            m = re.match(r"^/api/lesson/([a-f0-9]+)/comments$", path)
            if method == "GET" and m:
                return self._api_comments(conn, user, m.group(1))
            if method == "POST" and m:
                return self._api_comment_add(conn, user, m.group(1))
            # ----- v2 : feedback à chaud (élève) -----
            if path == "/api/feedback" and method == "POST":
                return self._api_feedback(conn, user)
            m = re.match(r"^/api/certificate/([a-f0-9]+)$", path)
            if method == "POST" and m:
                return self._api_certificate(conn, user, m.group(1))
            m = re.match(r"^/api/certificate/([a-f0-9]+)/$", path)
            if method == "GET" and m:
                return self._api_certificate(conn, user, m.group(1))
            if path == "/api/my/announcements" and method == "GET":
                return self._api_my_announcements(conn, user)
            if path == "/api/my/school" and method == "GET":
                return self._api_my_school(conn, user)

            # admin d'école
            if user["role"] != "student":
                if path == "/api/admin/overview" and method == "GET":
                    return self._api_admin_overview(conn, user)
                if path == "/api/admin/courses" and method == "GET":
                    return self._api_admin_courses(conn, user)
                if path == "/api/admin/courses" and method == "POST":
                    return self._api_admin_course_create(conn, user)
                m = re.match(r"^/api/admin/course/([a-f0-9]+)$", path)
                if m:
                    return self._api_admin_course(conn, user, method, m.group(1))
                m = re.match(r"^/api/admin/course/([a-f0-9]+)/module$", path)
                if method == "POST" and m:
                    return self._api_admin_module_create(conn, user, m.group(1))
                m = re.match(r"^/api/admin/module/([a-f0-9]+)$", path)
                if m:
                    return self._api_admin_module(conn, user, method, m.group(1))
                m = re.match(r"^/api/admin/module/([a-f0-9]+)/lesson$", path)
                if method == "POST" and m:
                    return self._api_admin_lesson_create(conn, user, m.group(1))
                m = re.match(r"^/api/admin/lesson/([a-f0-9]+)$", path)
                if m:
                    return self._api_admin_lesson(conn, user, method, m.group(1))
                m = re.match(r"^/api/admin/lesson/([a-f0-9]+)/pdf$", path)
                if method == "POST" and m:
                    return self._api_admin_lesson_pdf(conn, user, m.group(1))
                if path == "/api/admin/students" and method == "GET":
                    return self._api_admin_students(conn, user)
                if path == "/api/admin/enroll" and method == "POST":
                    return self._api_admin_enroll(conn, user)
                m = re.match(r"^/api/admin/enrollment/([a-f0-9]+)$", path)
                if method == "DELETE" and m:
                    return self._api_admin_unenroll(conn, user, m.group(1))
                if path == "/api/admin/codes" and method == "GET":
                    return self._api_admin_codes(conn, user)
                if path == "/api/admin/codes" and method == "POST":
                    return self._api_admin_codes_create(conn, user)
                m = re.match(r"^/api/admin/code/([a-f0-9]+)$", path)
                if method == "DELETE" and m:
                    return self._api_admin_code_revoke(conn, user, m.group(1))
                if path == "/api/admin/announcements" and method == "GET":
                    return self._api_admin_announcements(conn, user)
                if path == "/api/admin/announcements" and method == "POST":
                    return self._api_admin_announcement_create(conn, user)
                m = re.match(r"^/api/admin/announcement/([a-f0-9]+)$", path)
                if method == "DELETE" and m:
                    return self._api_admin_announcement_delete(conn, user, m.group(1))
                if path == "/api/admin/leads" and method == "GET":
                    return self._api_admin_leads(conn, user)
                m2 = re.match(r"^/api/admin/attendance/([a-f0-9]+)$", path)
                if method == "POST" and m2:
                    return self._api_admin_attendance(conn, user, m2.group(1))
                if path == "/api/admin/packs" and method == "GET":
                    return self._api_admin_packs(conn, user)
                if path == "/api/admin/packs" and method == "POST":
                    return self._api_admin_pack_create(conn, user)
                m = re.match(r"^/api/admin/pack/([a-f0-9]+)$", path)
                if m:
                    return self._api_admin_pack(conn, user, method, m.group(1))
                m = re.match(r"^/api/admin/pack/([a-f0-9]+)/courses$", path)
                if method == "POST" and m:
                    return self._api_admin_pack_courses(conn, user, m.group(1))
                if path == "/api/admin/feedback" and method == "GET":
                    return self._api_admin_feedback(conn, user)
                if path == "/api/admin/students" and method == "PATCH":
                    return self._api_admin_student_tags(conn, user)
                if path == "/api/admin/school" and method == "GET":
                    return self._api_admin_school(conn, user)
                if path == "/api/admin/school" and method == "PATCH":
                    return self._api_admin_school_patch(conn, user)

            # superadmin
            if user["role"] == "superadmin":
                if path == "/api/super/schools" and method == "GET":
                    return self._api_super_schools(conn)
                if path == "/api/super/schools" and method == "POST":
                    return self._api_super_school_create(conn)
                m = re.match(r"^/api/super/school/([a-f0-9]+)/admin$", path)
                if method == "POST" and m:
                    return self._api_super_school_admin_create(conn, m.group(1))

            return self._json({"error": "not_found", "path": path}, code=404)
        finally:
            conn.close()

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _static(self, filename: str, sub: str = None):
        if sub:
            path = os.path.join(STATIC_DIR, sub, filename)
        else:
            path = os.path.join(STATIC_DIR, filename)
        if not os.path.isfile(path) or "/" in filename or ".." in filename:
            return self._json({"error": "not_found"}, code=404)
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            body = f.read()
        self._send(200, body, ctype)

    def _serve_pdf(self, lesson_id: str):
        conn = db.get_conn()
        try:
            user = auth.user_from_token(conn, self._get_cookie_token())
            if not user:
                return self._json({"error": "unauthorized"}, code=401)
            lesson = db.q1(conn, "SELECT * FROM lessons WHERE id=?", (lesson_id,))
            if not lesson or not lesson["pdf_data"]:
                return self._json({"error": "not_found"}, code=404)
            course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (lesson["course_id"],))
            # autorisé si étudiant inscrit, ou admin de l'école
            ok = False
            if user["role"] == "student":
                ok = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=?",
                           (user["id"], lesson["course_id"])) is not None
            elif user["role"] == "superadmin":
                ok = True
            elif user["school_id"] == course["school_id"]:
                ok = True
            if not ok:
                return self._json({"error": "forbidden"}, code=403)
            name = lesson["pdf_name"] or "support.pdf"
            self._send(200, lesson["pdf_data"], "application/pdf",
                       extra=[("Content-Disposition", f'attachment; filename="{name}"')])
        finally:
            conn.close()

    # ==================================================================
    # Pages (templates HTML)
    # ==================================================================
    def _school_by_slug(self, conn, slug: str):
        return db.q1(conn, "SELECT * FROM schools WHERE slug=?", (slug,))

    def _page_landing(self, conn, user):
        if user:
            return self._redirect("/app")
        with open(os.path.join(STATIC_DIR, "landing.html")) as f:
            html = f.read()
        school = self._school_by_slug(conn, DEFAULT_SCHOOL_SLUG)
        school_id = school["id"] if school else None
        courses = db.q(conn, "SELECT id, slug, title, subtitle, level, price, old_price, duration_hours, color_card, cover_url "
                             "FROM courses WHERE school_id=? AND status='published' ORDER BY position, created_at", (school_id,))
        payload = {
            "school": db_row_to_dict(school) or {"name": "CDB Bien-Être", "slug": DEFAULT_SCHOOL_SLUG, "accent": "sage", "tagline": "Ressources & parcours des praticiens accompagnés"},
            "courses": [db_row_to_dict(c) for c in courses],
        }
        html = html.replace("{{DATA}}", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
        return self._html(html)

    def _page_course(self, conn, user, slug: str):
        with open(os.path.join(STATIC_DIR, "course.html")) as f:
            html = f.read()
        course = db.q1(conn, """SELECT c.*, s.slug AS school_slug, s.accent, s.name AS school_name
                                FROM courses c JOIN schools s ON s.id=c.school_id
                                WHERE c.slug=? AND c.status='published'""", (slug,))
        if not course:
            return self._html("<h1>Formation introuvable</h1><a href='/'>Retour</a>", code=404)
        c = db_row_to_dict(course)
        c.pop("created_at", None)
        c.pop("position", None)
        modules = db.q(conn, "SELECT m.id, m.title, m.description, m.position FROM modules m WHERE m.course_id=? ORDER BY m.position", (course["id"],))
        mods_json = []
        for mod in modules:
            lessons = db.q(conn, "SELECT id, title, position, free_preview, video_url FROM lessons WHERE module_id=? ORDER BY position", (mod["id"],))
            mods_json.append({
                "title": mod["title"], "description": mod["description"], "position": mod["position"],
                "lessons": [{"title": l["title"], "free": bool(l["free_preview"]), "has_video": bool(l["video_url"])} for l in lessons],
            })
        payload = {"school": {"name": c["school_name"], "accent": c["accent"]}, "course": c, "modules": mods_json}
        html = html.replace("{{DATA}}", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
        return self._html(html)

    def _page_login(self, mode: str = "login"):
        with open(os.path.join(STATIC_DIR, "login.html")) as f:
            html = f.read()
        html = html.replace("{{MODE}}", mode)
        return self._html(html)

    def _page_app(self, conn, user):
        with open(os.path.join(STATIC_DIR, "app.html")) as f:
            html = f.read()
        boot = {"id": user["id"], "email": user["email"], "name": user["name"],
                "role": user["role"], "school_id": user["school_id"]}
        html = html.replace("{{BOOT}}", json.dumps(boot, ensure_ascii=False).replace("</", "<\\/"))
        return self._html(html)

    # ==================================================================
    # API publiques
    # ==================================================================
    def _api_public_courses(self, conn):
        school = self._school_by_slug(conn, DEFAULT_SCHOOL_SLUG)
        courses = db.q(conn, "SELECT id, slug, title, subtitle, level, price, old_price, duration_hours, color_card, cover_url "
                             "FROM courses WHERE school_id=? AND status='published' ORDER BY position, created_at",
                       (school["id"] if school else None,))
        self._json([db_row_to_dict(c) for c in courses])

    def _api_public(self, conn, method, path):
        origin = self.headers.get("Origin", "")
        if method == "POST" and path == "/api/public/lead":
            try:
                body = self._body()
            except Exception:
                body = {}
            name = (body.get("name") or "").strip()[:120]
            email = (body.get("email") or "").strip().lower()[:200]
            goal = (body.get("goal") or "").strip()[:2000]
            school_slug = (body.get("school") or DEFAULT_SCHOOL_SLUG).strip()
            if not email or "@" not in email:
                return self._json({"error": "email manquant"}, code=400, cors_origin=origin or "null")
            school = self._school_by_slug(conn, school_slug)
            school_id = school["id"] if school else None
            existing = db.q1(conn, "SELECT id, school_id FROM leads WHERE email=? AND school_id=?", (email, school_id))
            if existing:
                db.ex(conn, "UPDATE leads SET goal=? WHERE id=? AND goal=''", (goal, existing["id"]))
                return self._json({"ok": True, "status": "already"}, cors_origin=origin or "null")
            db.ex(conn, "INSERT INTO leads (id, school_id, name, email, goal, source, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                  (db.new_id(), school_id, name, email, goal, "landing", "nouveau", db.now()))
            return self._json({"ok": True, "status": "created"}, code=201, cors_origin=origin or "null")
        return self._json({"error": "not_found"}, code=404, cors_origin=origin)

    def _api_signup(self, conn):
        body = self._body()
        email = (body.get("email") or "").strip().lower()
        pw = body.get("password") or ""
        name = (body.get("name") or "").strip()
        school_slug = (body.get("school") or DEFAULT_SCHOOL_SLUG).strip()
        if not email or "@" not in email or len(pw) < 6:
            return self._json({"error": "email invalide ou mot de passe < 6 caractères"}, code=400)
        if db.q1(conn, "SELECT id FROM users WHERE email=?", (email,)):
            return self._json({"error": "un compte existe déjà avec cet email"}, code=409)
        existing = db.q(conn, "SELECT id FROM users")
        school = self._school_by_slug(conn, school_slug)
        school_id = school["id"] if school else None
        is_first = len(existing) == 0
        role = "superadmin" if is_first else "student"
        uid = db.new_id()
        db.ex(conn, "INSERT INTO users (id, email, password_hash, name, role, school_id, created_at) VALUES (?,?,?,?,?,?,?)",
              (uid, email, auth.hash_password(pw), name or email.split("@")[0], role, school_id, db.now()))
        token = auth.create_session(conn, uid)
        return self._json({"ok": True, "role": role}, cookies=[self._cookie(token)])

    def _api_login(self, conn):
        body = self._body()
        email = (body.get("email") or "").strip().lower()
        pw = body.get("password") or ""
        user = db.q1(conn, "SELECT * FROM users WHERE email=?", (email,))
        if not user or not auth.verify_password(pw, user["password_hash"]):
            return self._json({"error": "email ou mot de passe incorrect"}, code=401)
        token = auth.create_session(conn, user["id"])
        return self._json({"ok": True, "role": user["role"]}, cookies=[self._cookie(token)])

    # ==================================================================
    # API étudiant
    # ==================================================================
    def _api_me(self, conn, user):
        if user["school_id"]:
            school = db.q1(conn, "SELECT id, name, slug, accent, tagline FROM schools WHERE id=?", (user["school_id"],))
        else:
            school = self._school_by_slug(conn, DEFAULT_SCHOOL_SLUG)   # superadmin → école par défaut
        adminish = user["role"] in ("school_admin", "superadmin")
        data = {"user": auth.sanitize_user(user),
                "school": db_row_to_dict(school),
                "is_admin": adminish,
                "is_super": user["role"] == "superadmin"}
        return self._json(data)

    def _my_course_ids(self, conn, user):
        return [r["course_id"] for r in db.q(conn, "SELECT course_id FROM enrollments WHERE user_id=? AND status='active'", (user["id"],))]

    def _api_redeem(self, conn, user):
        body = self._body()
        raw = (body.get("code") or "").strip().upper()
        if not raw:
            return self._json({"error": "code requis"}, code=400)
        code = db.q1(conn, "SELECT * FROM access_codes WHERE code=?", (raw,))
        if not code or code["status"] == "revoked":
            return self._json({"error": "code invalide"}, code=404)
        if code["status"] == "used":
            if code["used_by"] == user["id"]:
                # déjà utilisé par soi → r'assurer l'inscription
                if code["course_id"]:
                    db.ex(conn, "INSERT OR IGNORE INTO enrollments (id, user_id, course_id, school_id, source, code, status, enrolled_at) VALUES (?,?,?,?,?,?,?,?)",
                          (db.new_id(), user["id"], code["course_id"], code["school_id"], "code", raw, "active", db.now()))
                    return self._json({"ok": True, "already": True, "course_id": code["course_id"]})
            return self._json({"error": "code déjà utilisé"}, code=409)
        if code["pack_id"]:
            # ----- code pack : enrolle TOUTES les formations publiées du pack -----
            p = db.q1(conn, "SELECT * FROM packs WHERE id=?", (code["pack_id"],))
            if not p:
                return self._json({"error": "pack introuvable"}, code=404)
            already = db.q1(conn, "SELECT id FROM enrollments e JOIN pack_courses pc ON pc.course_id=e.course_id WHERE e.user_id=? AND pc.pack_id=?", (user["id"], code["pack_id"]))
            pcids = db.q(conn, "SELECT course_id FROM pack_courses WHERE pack_id=?", (code["pack_id"],))
            n = 0
            for row in pcids:
                cid = row["course_id"]
                conn.execute("INSERT OR IGNORE INTO enrollments (id, user_id, course_id, school_id, source, code, status, enrolled_at) VALUES (?,?,?,?,?,?,?,?)",
                             (db.new_id(), user["id"], cid, code["school_id"], "pack", raw, "active", db.now()))
                n += 1
            conn.commit()
            db.ex(conn, "UPDATE access_codes SET status='used', used_by=?, used_at=? WHERE id=?", (user["id"], db.now(), code["id"]))
            return self._json({"ok": True, "pack": {"id": p["id"], "title": p["title"]}, "courses_enrolled": n}, code=201)
        if not code["course_id"]:
            return self._json({"error": "code non associé à une formation"}, code=400)
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (code["course_id"],))
        if not course:
            return self._json({"error": "formation introuvable"}, code=404)
        db.ex(conn, "INSERT OR IGNORE INTO enrollments (id, user_id, course_id, school_id, source, code, status, enrolled_at) VALUES (?,?,?,?,?,?,?,?)",
              (db.new_id(), user["id"], course_id := code["course_id"], code["school_id"], "code", raw, "active", db.now()))
        db.ex(conn, "UPDATE access_codes SET status='used', used_by=?, used_at=? WHERE id=?", (user["id"], db.now(), code["id"]))
        return self._json({"ok": True, "course_id": course["id"], "course_title": course["title"]}, code=201)

    def _api_my_courses(self, conn, user):
        rows = db.q(conn, """
            SELECT e.id AS enroll_id, e.course_id, e.enrolled_at, e.source, e.status AS enroll_status,
                   c.title, c.subtitle, c.level, c.slug, c.duration_hours, c.color_card, c.cover_url
            FROM enrollments e JOIN courses c ON c.id = e.course_id
            WHERE e.user_id=?
            ORDER BY e.enrolled_at DESC""", (user["id"],))
        out = []
        for r in rows:
            total = db.q1(conn, "SELECT COUNT(*) AS n FROM lessons WHERE course_id=?", (r["course_id"],))["n"]
            done = db.q1(conn, "SELECT COUNT(*) AS n FROM progress WHERE user_id=? AND course_id=?", (user["id"], r["course_id"]))["n"]
            pct = int(100 * done / total) if total else 0
            cert = db.q1(conn, "SELECT serial FROM certificates WHERE user_id=? AND course_id=?", (user["id"], r["course_id"]))
            out.append({**db_row_to_dict(r), "total_lessons": total, "done_lessons": done, "progress_pct": pct,
                        "certificate_serial": cert["serial"] if cert else None})
        return self._json(out)

    def _course_outline(self, conn, user, course, with_progress=True):
        mods = db.q(conn, "SELECT * FROM modules WHERE course_id=? ORDER BY position", (course["id"],))
        done_set = set()
        if with_progress:
            done_set = {r["lesson_id"] for r in db.q(conn, "SELECT lesson_id FROM progress WHERE user_id=? AND course_id=?", (user["id"], course["id"]))}
        n_free = 0
        out = []
        for i, mod in enumerate(mods):
            lessons = db.q(conn, "SELECT * FROM lessons WHERE module_id=? ORDER BY position, created_at", (mod["id"],))
            l_json = []
            for l in lessons:
                # drip: leçon verrouillée si drip_days > 0 et pas assez de leçons terminées
                locked = False
                if l["drip_days"] > 0 and with_progress:
                    done_count = len(done_set)
                    locked = done_count < l["drip_days"]
                first_free_unlock = (i == 0 and n_free < 1 and bool(l["free_preview"]))
                # drip par DATE précise : verrouillé tant que la date n'est pas passée
                if l["drip_date"] and with_progress and not (user["role"] != "student"):
                    try:
                        locked = locked or (l["drip_date"] > db.now()[:10])
                    except Exception:
                        pass
                entry = {
                    "id": l["id"], "title": l["title"], "position": l["position"],
                    "has_video": bool(l["video_url"]), "has_pdf": bool(l["pdf_data"]),
                    "free_preview": bool(l["free_preview"]), "drip": l["drip_days"], "drip_date": l["drip_date"],
                    "min_seconds": l["min_seconds"],
                    "locked": locked and not first_free_unlock,
                    "done": l["id"] in done_set,
                    "has_quiz": db.q1(conn, "SELECT id FROM quizzes WHERE lesson_id=?", (l["id"],)) is not None,
                }
                if entry["free_preview"] and first_free_unlock:
                    n_free += 1
                l_json.append(entry)
            out.append({"id": mod["id"], "title": mod["title"], "description": mod["description"],
                        "position": mod["position"], "lessons": l_json})
        return out

    def _api_my_course(self, conn, user, course_id):
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (course_id,))
        if not course:
            return self._json({"error": "not_found"}, code=404)
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], course_id))
        can_view_preview = course["status"] == "published" and (
            user["role"] == "superadmin" or (user["role"] == "school_admin" and user["school_id"] == course["school_id"]))
        if not enrolled and not can_view_preview:
            return self._json({"error": "not_enrolled"}, code=403)
        mods = self._course_outline(conn, user, course, with_progress=bool(enrolled) or can_view_preview)
        total = sum(len(m["lessons"]) for m in mods)
        done = sum(1 for m in mods for l in m["lessons"] if l["done"])
        pct = int(100 * done / total) if total else 0
        cert = db.q1(conn, "SELECT serial, issued_at FROM certificates WHERE user_id=? AND course_id=?", (user["id"], course_id))
        return self._json({"course": {k: course[k] for k in ("id", "slug", "title", "subtitle", "description_html", "level", "duration_hours", "color_card", "cover_url")},
                           "outline": mods, "total_lessons": total, "done_lessons": done, "progress_pct": pct,
                           "certificate": dict(cert) if cert else None})

    def _api_lesson(self, conn, user, lesson_id):
        lesson = db.q1(conn, "SELECT * FROM lessons WHERE id=?", (lesson_id,))
        if not lesson:
            return self._json({"error": "not_found"}, code=404)
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (lesson["course_id"],))
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], lesson["course_id"]))
        if not enrolled and not (lesson["free_preview"] and course["status"] == "published"):
            if not (user["role"] != "student" and user["school_id"] == course["school_id"]):
                return self._json({"error": "not_enrolled"}, code=403)
        if enrolled:
            outline = self._course_outline(conn, user, course)
            lesson_meta = None
            for m in outline:
                for l in m["lessons"]:
                    if l["id"] == lesson_id:
                        lesson_meta = (m, l)
            if lesson_meta and lesson_meta[1]["locked"] and not lesson_meta[1]["free_preview"]:
                return self._json({"error": "locked", "drip_days": lesson["drip_days"]}, code=403)
        quiz = db.q1(conn, "SELECT id, title, pass_score FROM quizzes WHERE lesson_id=?", (lesson_id,))
        quiz_id = quiz["id"] if quiz else None
        # suivant / précédent
        flat = []
        mods = db.q(conn, "SELECT id FROM modules WHERE course_id=? ORDER BY position", (course["id"],))
        for m in mods:
            flat += [{"id": l["id"], "title": l["title"]} for l in db.q(conn, "SELECT id, title FROM lessons WHERE module_id=? ORDER BY position", (m["id"],))]
        idx = next((i for i, x in enumerate(flat) if x["id"] == lesson_id), None)
        prev = flat[idx - 1] if idx and idx > 0 else None
        nxt = flat[idx + 1] if idx is not None and idx + 1 < len(flat) else None
        done = db.q1(conn, "SELECT completed_at FROM progress WHERE user_id=? AND lesson_id=?", (user["id"], lesson_id))
        trow = db.q1(conn, "SELECT seconds FROM lesson_time WHERE user_id=? AND lesson_id=?", (user["id"], lesson_id))
        return self._json({
            "lesson": {"id": lesson["id"], "title": lesson["title"], "content_html": lesson["content_html"],
                       "video_url": lesson["video_url"], "pdf_name": lesson["pdf_name"],
                       "pdf_url": (f"/pdf/{lesson['id']}" if lesson["pdf_data"] else None),
                       "min_seconds": lesson["min_seconds"], "drip_date": lesson["drip_date"],
                       "seconds_spent": trow["seconds"] if trow else 0,
                       "done": bool(done), "completed_at": done["completed_at"] if done else None},
            "course": {"id": course["id"], "title": course["title"], "slug": course["slug"]},
            "quiz_id": quiz_id, "quiz_title": quiz["title"] if quiz else None, "quiz_pass_score": quiz["pass_score"] if quiz else None,
            "prev": prev, "next": nxt})

    def _api_progress(self, conn, user):
        body = self._body()
        lesson_id = body.get("lesson_id")
        lesson = db.q1(conn, "SELECT course_id, min_seconds FROM lessons WHERE id=?", (lesson_id,))
        if not lesson:
            return self._json({"error": "not_found"}, code=404)
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], lesson["course_id"]))
        if not enrolled:
            return self._json({"error": "not_enrolled"}, code=403)
        # garde-fou Qualiopi : durée minimum de visionnage actif (s'il est configuré)
        if lesson["min_seconds"] and lesson["min_seconds"] > 0:
            trow = db.q1(conn, "SELECT seconds FROM lesson_time WHERE user_id=? AND lesson_id=?", (user["id"], lesson_id))
            spent = trow["seconds"] if trow else 0
            if spent < lesson["min_seconds"]:
                return self._json({"error": "min_time", "required_seconds": lesson["min_seconds"],
                                   "spent_seconds": spent,
                                   "message": "Lis encore un peu la leçon avant de la marquer comme terminée."},
                                  code=409)
        db.ex(conn, "INSERT OR IGNORE INTO progress (id, user_id, lesson_id, course_id, completed_at) VALUES (?,?,?,?,?)",
              (db.new_id(), user["id"], lesson_id, lesson["course_id"], db.now()))
        return self._json({"ok": True})

    def _api_lesson_time(self, conn, user):
        """Tick de temps actif : le front n'appelle que si document.visibilityState == 'visible'."""
        body = self._body()
        lesson_id = body.get("lesson_id")
        secs = max(0, min(int(body.get("seconds", 0)), 60))   # 1 tick max 60 s
        lesson = db.q1(conn, "SELECT course_id FROM lessons WHERE id=?", (lesson_id,))
        if not lesson:
            return self._json({"error": "not_found"}, code=404)
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], lesson["course_id"]))
        if not enrolled:
            return self._json({"error": "not_enrolled"}, code=403)
        if secs <= 0:
            return self._json({"ok": True})
        db.ex(conn, """INSERT INTO lesson_time (id, user_id, lesson_id, course_id, seconds, updated_at)
                       VALUES (?,?,?,?,?,?)
                       ON CONFLICT(user_id, lesson_id) DO UPDATE SET
                           seconds = seconds + excluded.seconds, updated_at = excluded.updated_at""",
              (db.new_id(), user["id"], lesson_id, lesson["course_id"], secs, db.now()))
        return self._json({"ok": True})

    def _api_quiz(self, conn, user, quiz_id):
        quiz = db.q1(conn, "SELECT * FROM quizzes WHERE id=?", (quiz_id,))
        if not quiz:
            return self._json({"error": "not_found"}, code=404)
        lesson = db.q1(conn, "SELECT course_id FROM lessons WHERE id=?", (quiz["lesson_id"],))
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], lesson["course_id"]))
        if not enrolled:
            return self._json({"error": "not_enrolled"}, code=403)
        questions = db.q(conn, "SELECT id, question, options, position FROM quiz_questions WHERE quiz_id=? ORDER BY position", (quiz_id,))
        return self._json({"quiz": {"id": quiz["id"], "title": quiz["title"], "pass_score": quiz["pass_score"]},
                           "questions": [{"id": x["id"], "question": x["question"], "options": json.loads(x["options"])} for x in questions]})

    def _api_quiz_attempt(self, conn, user, quiz_id):
        body = self._body()
        quiz = db.q1(conn, "SELECT * FROM quizzes WHERE id=?", (quiz_id,))
        if not quiz:
            return self._json({"error": "not_found"}, code=404)
        lesson = db.q1(conn, "SELECT course_id FROM lessons WHERE id=?", (quiz["lesson_id"],))
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], lesson["course_id"]))
        if not enrolled:
            return self._json({"error": "not_enrolled"}, code=403)
        answers = body.get("answers") or {}   # {question_id: index}
        questions = db.q(conn, "SELECT * FROM quiz_questions WHERE quiz_id=? ORDER BY position", (quiz_id,))
        results = []
        score = 0
        for x in questions:
            given = answers.get(x["id"])
            correct = (given is not None and int(given) == x["correct"])
            score += 1 if correct else 0
            opts = json.loads(x["options"])
            results.append({"id": x["id"], "question": x["question"], "options": opts,
                            "given": given, "correct_index": x["correct"], "ok": correct,
                            "explanation": x["explanation"]})
        max_score = len(questions)
        pct = int(100 * score / max_score) if max_score else 0
        passed = pct >= quiz["pass_score"]
        db.ex(conn, "INSERT INTO quiz_attempts (id, user_id, quiz_id, score, max_score, passed, answers, taken_at) VALUES (?,?,?,?,?,?,?,?)",
              (db.new_id(), user["id"], quiz_id, score, max_score, 1 if passed else 0,
               json.dumps(answers, ensure_ascii=False), db.now()))
        return self._json({"score": score, "max_score": max_score, "pct": pct, "passed": passed, "results": results})

    def _api_certificate(self, conn, user, course_id):
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (course_id,))
        if not course:
            return self._json({"error": "not_found"}, code=404)
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=?", (user["id"], course_id))
        if not enrolled:
            return self._json({"error": "not_enrolled"}, code=403)
        total = db.q1(conn, "SELECT COUNT(*) AS n FROM lessons WHERE course_id=?", (course_id,))["n"]
        done = db.q1(conn, "SELECT COUNT(*) AS n FROM progress WHERE user_id=? AND course_id=?", (user["id"], course_id))["n"]
        # quiz : tous les quiz du cours réussis
        quizzes = db.q(conn, "SELECT q.id, q.pass_score FROM quizzes q JOIN lessons l ON l.id=q.lesson_id WHERE l.course_id=?", (course_id,))
        passed_ok = True
        for qq in quizzes:
            best = db.q1(conn, "SELECT MAX(pct) FROM (SELECT CASE WHEN score >= max_score THEN 100 ELSE ROUND(100.0*score/max_score) END AS pct FROM quiz_attempts WHERE user_id=? AND quiz_id=?)",
                         (user["id"], qq["id"]))
            bpct = best[0] if best and best[0] is not None else 0
            if bpct < qq["pass_score"]:
                passed_ok = False
        if total == 0 or done < total or not passed_ok:
            return self._json({"eligible": False, "done": done, "total": total, "quizzes_ok": passed_ok}, code=200)
        existing = db.q1(conn, "SELECT * FROM certificates WHERE user_id=? AND course_id=?", (user["id"], course_id))
        if existing:
            return self._json({"eligible": True, "certificate": db_row_to_dict(existing)})
        serial = f"BLW-{course['slug'][:7].upper()}-{db.new_id()[:6].upper()}"
        db.ex(conn, "INSERT INTO certificates (id, user_id, course_id, serial, kind, student_name, course_title, issued_at) VALUES (?,?,?,?,?,?,?,?)",
              (db.new_id(), user["id"], course_id, serial, "reussite", user["name"] or user["email"], course["title"], db.now()))
        cert = db.q1(conn, "SELECT * FROM certificates WHERE user_id=? AND course_id=?", (user["id"], course_id))
        db.ex(conn, "UPDATE enrollments SET status='completed' WHERE user_id=? AND course_id=?", (user["id"], course_id))
        return self._json({"eligible": True, "certificate": db_row_to_dict(cert)}, code=201)

    # ==================================================================
    # v2 — commentaires coach↔élève, feedback à chaud, assist. assiduité
    # ==================================================================
    def _api_comments(self, conn, user, lesson_id):
        lesson = db.q1(conn, "SELECT course_id FROM lessons WHERE id=?", (lesson_id,))
        if not lesson:
            return self._json({"error": "not_found"}, code=404)
        course = db.q1(conn, "SELECT school_id FROM courses WHERE id=?", (lesson["course_id"],))
        is_coach = user["role"] != "student" and (user["role"] == "superadmin" or user["school_id"] == course["school_id"])
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], lesson["course_id"]))
        if not enrolled and not is_coach:
            return self._json({"error": "not_enrolled"}, code=403)
        # un coach peut voir le fil de N'IMPORTE quel élève (via ?student=) ; un élève ne voit que le sien
        target_id = user["id"]
        if is_coach and user["role"] != "student":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            target_id = (qs.get("student") or [user["id"]])[0]
        rows = db.q(conn, """SELECT c.id, c.body, c.created_at, c.author_role, u.name author_name, u.email author_email
                             FROM lesson_comments c LEFT JOIN users u ON u.id=c.author_id
                             WHERE c.lesson_id=? AND c.user_id=? ORDER BY c.created_at""", (lesson_id, target_id))
        return self._json({"comments": [db_row_to_dict(r) for r in rows],
                           "can_reply": bool(is_coach), "thread_owner": target_id == user["id"]})

    def _api_comment_add(self, conn, user, lesson_id):
        lesson = db.q1(conn, "SELECT course_id FROM lessons WHERE id=?", (lesson_id,))
        if not lesson:
            return self._json({"error": "not_found"}, code=404)
        course = db.q1(conn, "SELECT school_id FROM courses WHERE id=?", (lesson["course_id"],))
        is_coach = user["role"] != "student" and (user["role"] == "superadmin" or user["school_id"] == course["school_id"])
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], lesson["course_id"]))
        if not enrolled and not is_coach:
            return self._json({"error": "not_enrolled"}, code=403)
        body = self._body()
        body_txt = ((body.get("body") or "")).strip()[:3000]
        if not body_txt:
            return self._json({"error": "message vide"}, code=400)
        # le coach répond dans le fil d'un élève précis (body.student) ; l'élève écrit dans le sien
        target_id = user["id"]
        if is_coach and user["role"] != "student":
            st = (body.get("student") or "").strip()
            target_id = st if st else user["id"]
            if st and not db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=?", (st, lesson["course_id"])):
                return self._json({"error": "cet élève n'est pas inscrit à cette formation"}, code=404)
        db.ex(conn, "INSERT INTO lesson_comments (id, lesson_id, user_id, author_id, author_role, body, created_at) VALUES (?,?,?,?,?,?,?)",
              (db.new_id(), lesson_id, target_id, user["id"], "coach" if is_coach else "student", body_txt, db.now()))
        return self._json({"ok": True}, code=201)

    def _api_feedback(self, conn, user):
        body = self._body()
        course_id = body.get("course_id")
        rating = max(1, min(int(body.get("rating", 5)), 5))
        comment = (body.get("comment") or "").strip()[:2000]
        course = db.q1(conn, "SELECT school_id FROM courses WHERE id=?", (course_id,))
        if not course:
            return self._json({"error": "not_found"}, code=404)
        enrolled = db.q1(conn, "SELECT id FROM enrollments WHERE user_id=? AND course_id=? AND status='active'", (user["id"], course_id))
        if not enrolled:
            return self._json({"error": "not_enrolled"}, code=403)
        # satisfaction à chaud : possible seulement à 100 % de complétion
        total = db.q1(conn, "SELECT COUNT(*) n FROM lessons WHERE course_id=?", (course_id,))["n"]
        done = db.q1(conn, "SELECT COUNT(*) n FROM progress WHERE user_id=? AND course_id=?", (user["id"], course_id))["n"]
        if total and done < total:
            return self._json({"error": "feedback_possible_a_100_pct"}, code=409)
        db.ex(conn, "INSERT OR REPLACE INTO feedback (id, school_id, course_id, user_id, rating, comment, created_at) VALUES (?,?,?,?,?,?,?)",
              (db.new_id(), course["school_id"], course_id, user["id"], rating, comment, db.now()))
        return self._json({"ok": True}, code=201)

    def _api_admin_feedback(self, conn, user):
        school_id = self._default_school_id(conn, user)
        rows = db.q(conn, """SELECT f.rating, f.comment, f.created_at, u.name student_name, c.title course_title
                             FROM feedback f LEFT JOIN users u ON u.id=f.user_id
                             LEFT JOIN courses c ON c.id=f.course_id
                             WHERE f.school_id=? ORDER BY f.created_at DESC LIMIT 100""", (school_id,))
        return self._json([db_row_to_dict(r) for r in rows])

    def _api_admin_attendance(self, conn, user, user_id):
        """Attestation d'assiduité (≥80 % complétion) — Qualiopi."""
        body = self._body()
        course_id = body.get("course_id")
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (course_id,))
        if not course or not self._can_school(conn, user, course["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        target = db.q1(conn, "SELECT * FROM users WHERE id=?", (user_id,))
        if not target:
            return self._json({"error": "élève introuvable"}, code=404)
        total = db.q1(conn, "SELECT COUNT(*) n FROM lessons WHERE course_id=?", (course_id,))["n"]
        done = db.q1(conn, "SELECT COUNT(*) n FROM progress WHERE user_id=? AND course_id=?", (user_id, course_id))["n"]
        pct = int(100 * done / total) if total else 0
        if pct < 80:
            return self._json({"error": "assiduité non atteinte (80 % minimum requis)", "pct": pct}, code=409)
        existing = db.q1(conn, "SELECT id FROM certificates WHERE user_id=? AND course_id=? AND kind='assiduite'", (user_id, course_id))
        if existing:
            return self._json({"ok": True, "already": True})
        serial = f"BLW-ASS-{course['slug'][:5].upper()}-{db.new_id()[:6].upper()}"
        db.ex(conn, "INSERT INTO certificates (id, user_id, course_id, serial, kind, student_name, course_title, issued_at) VALUES (?,?,?,?,?,?,?,?)",
              (db.new_id(), user_id, course_id, serial, "assiduite", target["name"] or target["email"], course["title"], db.now()))
        return self._json({"ok": True, "serial": serial}, code=201)

    def _api_admin_student_tags(self, conn, user):
        body = self._body()
        uid = body.get("user_id")
        tags = (body.get("tags") or "").strip()[:400]
        target = db.q1(conn, "SELECT * FROM users WHERE id=?", (uid,))
        if not target:
            return self._json({"error": "élève introuvable"}, code=404)
        if user["role"] != "superadmin" and target["school_id"] != user["school_id"]:
            return self._json({"error": "forbidden"}, code=403)
        db.ex(conn, "UPDATE users SET tags=? WHERE id=?", (tags, uid))
        return self._json({"ok": True})

    def _api_my_announcements(self, conn, user):
        rows = db.q(conn, """SELECT a.id, a.title, a.body, a.created_at, c.title AS course_title, s.name AS school_name
                             FROM announcements a LEFT JOIN courses c ON c.id = a.course_id
                             LEFT JOIN schools s ON s.id = a.school_id
                             WHERE a.school_id=? ORDER BY a.created_at DESC LIMIT 20""", (user["school_id"],))
        return self._json([db_row_to_dict(r) for r in rows])

    def _api_my_school(self, conn, user):
        school = db.q1(conn, "SELECT * FROM schools WHERE id=?", (user["school_id"],)) if user["school_id"] else None
        if not school:
            school = self._school_by_slug(conn, DEFAULT_SCHOOL_SLUG)
        return self._json(db_row_to_dict(school) or {})

    # ==================================================================
    # API admin d'école
    # ==================================================================
    def _school_scope(self, conn, user):
        """school_id pour admin d'école (superadmin → école bienetre par défaut)."""
        if user["role"] == "school_admin" and user["school_id"]:
            return user["school_id"]
        return None  # superadmin doit préciser school_id dans le body

    def _can_school(self, conn, user, school_id):
        if user["role"] == "superadmin":
            return True
        return user["role"] == "school_admin" and user["school_id"] == school_id

    def _default_school_id(self, conn, user):
        """superadmin sans school_id → école par défaut (bienetre)."""
        if user["school_id"]:
            return user["school_id"]
        s = self._school_by_slug(conn, DEFAULT_SCHOOL_SLUG)
        return s["id"] if s else None

    def _api_admin_overview(self, conn, user):
        school_id = self._default_school_id(conn, user)
        if not school_id:
            return self._json({"error": "no_school"}, code=400)
        n_courses = db.q1(conn, "SELECT COUNT(*) n FROM courses WHERE school_id=?", (school_id,))["n"]
        n_published = db.q1(conn, "SELECT COUNT(*) n FROM courses WHERE school_id=? AND status='published'", (school_id,))["n"]
        n_students = db.q1(conn, "SELECT COUNT(DISTINCT e.user_id) n FROM enrollments e JOIN users u ON u.id=e.user_id WHERE e.school_id=? AND u.role='student'", (school_id,))["n"]
        n_leads = db.q1(conn, "SELECT COUNT(*) n FROM leads WHERE school_id=? AND status='nouveau'", (school_id,))["n"]
        n_codes_active = db.q1(conn, "SELECT COUNT(*) n FROM access_codes WHERE school_id=? AND status='active'", (school_id,))["n"]
        certs = db.q1(conn, "SELECT COUNT(*) n FROM certificates ce JOIN courses c ON c.id=ce.course_id WHERE c.school_id=?", (school_id,))["n"]
        # taux de complétion
        rows = db.q(conn, "SELECT e.course_id, c.title FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.school_id=?", (school_id,))
        completion = {}
        for r in rows:
            total = db.q1(conn, "SELECT COUNT(*) n FROM lessons WHERE course_id=?", (r["course_id"],))["n"]
            per_user = db.q(conn, "SELECT e.user_id, COUNT(p.id) done FROM enrollments e LEFT JOIN progress p ON p.user_id=e.user_id AND p.course_id=e.course_id WHERE e.course_id=? GROUP BY e.user_id", (r["course_id"],))
            if per_user:
                pcts = [int(100 * row["done"] / total) if total else 0 for row in per_user]
                completion[r["title"]] = int(sum(pcts) / len(pcts))
        recent = db.q(conn, """SELECT e.enrolled_at, u.name, u.email, c.title course_title
                               FROM enrollments e JOIN users u ON u.id=e.user_id JOIN courses c ON c.id=e.course_id
                               WHERE e.school_id=? ORDER BY e.enrolled_at DESC LIMIT 8""", (school_id,))
        return self._json({"counts": {"courses": n_courses, "published": n_published, "students": n_students,
                                      "new_leads": n_leads, "active_codes": n_codes_active, "certificates": certs},
                           "completion": completion,
                           "recent_enrollments": [db_row_to_dict(r) for r in recent]})

    def _api_admin_courses(self, conn, user):
        school_id = self._default_school_id(conn, user)
        if not school_id:
            return self._json([])
        rows = db.q(conn, "SELECT * FROM courses WHERE school_id=? ORDER BY position, created_at", (school_id,))
        out = []
        for r in rows:
            n_mod = db.q1(conn, "SELECT COUNT(*) n FROM modules WHERE course_id=?", (r["id"],))["n"]
            n_les = db.q1(conn, "SELECT COUNT(*) n FROM lessons WHERE course_id=?", (r["id"],))["n"]
            out.append({**db_row_to_dict(r), "modules": n_mod, "lessons": n_les})
        return self._json(out)

    def _api_admin_course_create(self, conn, user):
        body = self._body()
        school_id = user["school_id"]
        title = (body.get("title") or "").strip()
        if not school_id or not title:
            return self._json({"error": "titre obligatoire"}, code=400)
        slug = slugify(body.get("slug") or title)
        base, k = slug, 2
        while db.q1(conn, "SELECT id FROM courses WHERE school_id=? AND slug=?", (school_id, slug)):
            slug = f"{base}-{k}"; k += 1
        cid = db.new_id()
        db.ex(conn, """INSERT INTO courses (id, school_id, slug, title, subtitle, description_html, level, price, old_price, duration_hours, color_card, cover_url, status, position, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (cid, school_id, slug, title, body.get("subtitle", ""), body.get("description_html", ""),
               body.get("level", "débutant"), body.get("price", 0), body.get("old_price"), body.get("duration_hours", ""),
               body.get("color_card", ""), body.get("cover_url", ""), "draft",
               body.get("position", db.q1(conn, "SELECT COUNT(*) n FROM courses WHERE school_id=?", (school_id,))["n"]), db.now()))
        return self._json({"ok": True, "id": cid}, code=201)

    def _api_admin_course(self, conn, user, method, course_id):
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (course_id,))
        if not course or not self._can_school(conn, user, course["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        if method == "GET":
            mods = self._course_outline(conn, user, course, with_progress=False)
            return self._json({"course": {k: course[k] for k in course.keys()}, "outline": mods})
        if method == "PATCH":
            body = self._body()
            fields = ["title", "subtitle", "description_html", "level", "price", "old_price", "duration_hours", "color_card", "cover_url", "status"]
            sets, vals = [], []
            for f in fields:
                if f in body:
                    sets.append(f + "=?"); vals.append(body[f])
            if sets:
                vals.append(course_id)
                db.ex(conn, "UPDATE courses SET " + ", ".join(sets) + " WHERE id=?", tuple(vals))
            return self._json({"ok": True})
        if method == "DELETE":
            db.ex(conn, "DELETE FROM courses WHERE id=?", (course_id,))
            return self._json({"ok": True})

    def _api_admin_module_create(self, conn, user, course_id):
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (course_id,))
        if not course or not self._can_school(conn, user, course["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        body = self._body()
        title = (body.get("title") or "").strip()
        if not title:
            return self._json({"error": "titre obligatoire"}, code=400)
        mid = db.new_id()
        pos = body.get("position", db.q1(conn, "SELECT COUNT(*) n FROM modules WHERE course_id=?", (course_id,))["n"])
        db.ex(conn, "INSERT INTO modules (id, course_id, title, description, position) VALUES (?,?,?,?,?)",
              (mid, course_id, title, body.get("description", ""), pos))
        return self._json({"ok": True, "id": mid}, code=201)

    def _api_admin_module(self, conn, user, method, module_id):
        mod = db.q1(conn, "SELECT m.*, c.school_id FROM modules m JOIN courses c ON c.id=m.course_id WHERE m.id=?", (module_id,))
        if not mod or not self._can_school(conn, user, mod["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        if method == "PATCH":
            body = self._body()
            sets, vals = [], []
            for f in ("title", "description", "position"):
                if f in body:
                    sets.append(f + "=?"); vals.append(body[f])
            if sets:
                vals.append(module_id)
                db.ex(conn, "UPDATE modules SET " + ", ".join(sets) + " WHERE id=?", tuple(vals))
            return self._json({"ok": True})
        if method == "DELETE":
            db.ex(conn, "DELETE FROM modules WHERE id=?", (module_id,))
            return self._json({"ok": True})

    def _api_admin_lesson_create(self, conn, user, module_id):
        mod = db.q1(conn, "SELECT m.*, c.school_id FROM modules m JOIN courses c ON c.id=m.course_id WHERE m.id=?", (module_id,))
        if not mod or not self._can_school(conn, user, mod["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        body = self._body()
        title = (body.get("title") or "").strip() or "Leçon"
        lid = db.new_id()
        pos = body.get("position", db.q1(conn, "SELECT COUNT(*) n FROM lessons WHERE module_id=?", (module_id,))["n"])
        db.ex(conn, "INSERT INTO lessons (id, module_id, course_id, title, content_html, video_url, position, free_preview, drip_days, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (lid, module_id, mod["course_id"], title, body.get("content_html", ""), body.get("video_url", ""), pos,
               1 if body.get("free_preview") else 0, int(body.get("drip_days", 0)), db.now()))
        if body.get("quiz"):
            self._create_quiz(conn, lid, body.get("quiz_pass_score", 70), body["quiz"])
        return self._json({"ok": True, "id": lid}, code=201)

    def _create_quiz(self, conn, lesson_id, pass_score, questions):
        qid = db.new_id()
        db.ex(conn, "INSERT OR REPLACE INTO quizzes (id, lesson_id, title, pass_score) VALUES (?,?,?,?)",
              (qid, lesson_id, "Quiz du module", int(pass_score)))
        db.ex(conn, "DELETE FROM quiz_questions WHERE quiz_id=?", (qid,))
        for i, qq in enumerate(questions):
            db.ex(conn, "INSERT INTO quiz_questions (id, quiz_id, question, options, correct, explanation, position) VALUES (?,?,?,?,?,?,?)",
                  (db.new_id(), qid, qq.get("question", ""), json.dumps(qq.get("options", []), ensure_ascii=False),
                   int(qq.get("correct", 0)) if 0 <= int(qq.get("correct", 0)) < len(qq.get("options", [""])) else 0,
                   qq.get("explanation", ""), i))
        return qid

    def _api_admin_lesson(self, conn, user, method, lesson_id):
        les = db.q1(conn, "SELECT l.*, c.school_id FROM lessons l JOIN courses c ON c.id=l.course_id WHERE l.id=?", (lesson_id,))
        if not les or not self._can_school(conn, user, les["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        if method == "GET":
            quiz = db.q1(conn, "SELECT * FROM quizzes WHERE lesson_id=?", (lesson_id,))
            quiz_full = None
            if quiz:
                quiz_full = {"id": quiz["id"], "title": quiz["title"], "pass_score": quiz["pass_score"],
                             "questions": [dict(db_row_to_dict(x), options=json.loads(x["options"])) for x in
                                           db.q(conn, "SELECT * FROM quiz_questions WHERE quiz_id=? ORDER BY position", (quiz["id"],))]}
            return self._json({"lesson": {k: (les[k].decode("utf-8") if isinstance(les[k], bytes) else les[k]) for k in les.keys() if k != "pdf_data"},
                               "quiz": quiz_full})
        if method == "PATCH":
            body = self._body()
            sets, vals = [], []
            for f in ("title", "content_html", "video_url"):
                if f in body:
                    sets.append(f + "=?"); vals.append(body[f])
            if "free_preview" in body:
                sets.append("free_preview=?"); vals.append(1 if body["free_preview"] else 0)
            if "drip_days" in body:
                sets.append("drip_days=?"); vals.append(int(body["drip_days"]))
            if "position" in body:
                sets.append("position=?"); vals.append(int(body["position"]))
            if "pdf_name" in body:
                sets.append("pdf_name=?"); vals.append(body["pdf_name"])
            if sets:
                vals.append(lesson_id)
                db.ex(conn, "UPDATE lessons SET " + ", ".join(sets) + " WHERE id=?", tuple(vals))
            if "quiz" in body:
                if body["quiz"] is None:
                    db.ex(conn, "DELETE FROM quizzes WHERE lesson_id=?", (lesson_id,))
                else:
                    existing = db.q1(conn, "SELECT id FROM quizzes WHERE lesson_id=?", (lesson_id,))
                    if existing:
                        self._create_quiz(conn, lesson_id, body.get("quiz_pass_score", 70), body["quiz"])
                        # _create_quiz fait INSERT OR REPLACE → supprime les questions, ok
                    else:
                        self._create_quiz(conn, lesson_id, body.get("quiz_pass_score", 70), body["quiz"])
            return self._json({"ok": True})
        if method == "DELETE":
            db.ex(conn, "DELETE FROM lessons WHERE id=?", (lesson_id,))
            return self._json({"ok": True})

    def _api_admin_lesson_pdf(self, conn, user, lesson_id):
        les = db.q1(conn, "SELECT l.*, c.school_id FROM lessons l JOIN courses c ON c.id=l.course_id WHERE l.id=?", (lesson_id,))
        if not les or not self._can_school(conn, user, les["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        body = self._body()
        b64 = body.get("b64") or ""
        name = body.get("name") or "support.pdf"
        try:
            data = base64.b64decode(b64)
        except Exception:
            return self._json({"error": "base64 invalide"}, code=400)
        if len(data) > 12 * 1024 * 1024:
            return self._json({"error": "PDF trop volumineux (>12 Mo)"}, code=413)
        db.ex(conn, "UPDATE lessons SET pdf_data=?, pdf_name=? WHERE id=?", (data, name, lesson_id))
        return self._json({"ok": True, "bytes": len(data)})

    def _api_admin_students(self, conn, user):
        school_id = self._default_school_id(conn, user)
        if not school_id:
            return self._json([])
        rows = db.q(conn, """SELECT u.id, u.email, u.name, u.tags, u.created_at,
                             COUNT(DISTINCT e.course_id) n_courses,
                             SUM(CASE WHEN e.status='completed' THEN 1 ELSE 0 END) n_completed
                             FROM users u LEFT JOIN enrollments e ON e.user_id=u.id
                             WHERE u.school_id=? AND u.role='student'
                             GROUP BY u.id ORDER BY u.created_at DESC""", (school_id,))
        out = []
        for r in rows:
            enr = db.q(conn, """SELECT e.id AS enroll_id, e.status, e.enrolled_at, c.id AS course_id, c.title,
                                (SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) AS total,
                                (SELECT COUNT(*) FROM progress p WHERE p.user_id=e.user_id AND p.course_id=c.id) AS done
                                FROM enrollments e JOIN courses c ON c.id=e.course_id
                                WHERE e.user_id=? ORDER BY e.enrolled_at DESC""", (r["id"],))
            out.append({**db_row_to_dict(r),
                        "enrollments": [{"enroll_id": x["enroll_id"], "course_id": x["course_id"], "title": x["title"],
                                         "status": x["status"], "pct": int(100 * x["done"] / x["total"]) if x["total"] else 0}
                                        for x in enr]})
        return self._json(out)

    def _api_admin_enroll(self, conn, user):
        body = self._body()
        course_id = body.get("course_id")
        user_id = body.get("user_id")
        course = db.q1(conn, "SELECT * FROM courses WHERE id=?", (course_id,))
        if not course or not self._can_school(conn, user, course["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        target = db.q1(conn, "SELECT * FROM users WHERE id=?", (user_id,))
        if not target:
            return self._json({"error": "étudiant introuvable"}, code=404)
        db.ex(conn, "INSERT OR IGNORE INTO enrollments (id, user_id, course_id, school_id, source, status, enrolled_at) VALUES (?,?,?,?,?,?,?)",
              (db.new_id(), user_id, course_id, course["school_id"], "manual", "active", db.now()))
        return self._json({"ok": True}, code=201)

    def _api_admin_unenroll(self, conn, user, enroll_id):
        enr = db.q1(conn, "SELECT * FROM enrollments WHERE id=?", (enroll_id,))
        if not enr:
            return self._json({"error": "not_found"}, code=404)
        course = db.q1(conn, "SELECT school_id FROM courses WHERE id=?", (enr["course_id"],))
        if not self._can_school(conn, user, course["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        db.ex(conn, "DELETE FROM enrollments WHERE id=?", (enroll_id,))
        return self._json({"ok": True})

    def _api_admin_codes(self, conn, user):
        school_id = self._default_school_id(conn, user)
        if not school_id:
            return self._json([])
        rows = db.q(conn, """SELECT a.*, c.title course_title FROM access_codes a
                             LEFT JOIN courses c ON c.id = a.course_id WHERE a.school_id=? ORDER BY a.created_at DESC""", (school_id,))
        return self._json([{**db_row_to_dict(r)} for r in rows])

    def _api_admin_codes_create(self, conn, user):
        body = self._body()
        school_id = user["school_id"]
        count = min(int(body.get("count", 1)), 50)
        course_id = body.get("course_id")
        note = (body.get("note") or "").strip()
        pack_id = (body.get("pack_id") or "").strip() or None
        if pack_id:
            p = db.q1(conn, "SELECT * FROM packs WHERE id=?", (pack_id,))
            if not p or p["school_id"] != school_id:
                return self._json({"error": "pack introuvable"}, code=404)
        out = []
        for _ in range(count):
            code = "BLW-" + db.new_id()[:8].upper()
            cid = db.new_id()
            db.ex(conn, "INSERT INTO access_codes (id, school_id, course_id, pack_id, code, status, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
                  (cid, school_id, course_id, pack_id, code, "active", note, db.now()))
            out.append(code)
        return self._json({"ok": True, "codes": out}, code=201)

    def _api_admin_code_revoke(self, conn, user, code_id):
        code = db.q1(conn, "SELECT * FROM access_codes WHERE id=?", (code_id,))
        if not code or not self._can_school(conn, user, code["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        db.ex(conn, "UPDATE access_codes SET status='revoked' WHERE id=?", (code_id,))
        return self._json({"ok": True})

    def _api_admin_announcements(self, conn, user):
        school_id = self._default_school_id(conn, user)
        rows = db.q(conn, """SELECT a.*, c.title course_title FROM announcements a LEFT JOIN courses c ON c.id=a.course_id
                             WHERE a.school_id=? ORDER BY a.created_at DESC LIMIT 50""", (school_id,))
        return self._json([db_row_to_dict(r) for r in rows])

    def _api_admin_announcement_create(self, conn, user):
        body = self._body()
        title = (body.get("title") or "").strip()
        if not title:
            return self._json({"error": "titre obligatoire"}, code=400)
        db.ex(conn, "INSERT INTO announcements (id, school_id, course_id, title, body, created_at) VALUES (?,?,?,?,?,?)",
              (db.new_id(), user["school_id"], body.get("course_id"), title, body.get("body", ""), db.now()))
        return self._json({"ok": True}, code=201)

    def _api_admin_announcement_delete(self, conn, user, aid):
        row = db.q1(conn, "SELECT * FROM announcements WHERE id=?", (aid,))
        if not row or not self._can_school(conn, user, row["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        db.ex(conn, "DELETE FROM announcements WHERE id=?", (aid,))
        return self._json({"ok": True})

    # ==================================================================
    # v2 — admin packs
    # ==================================================================
    def _api_admin_packs(self, conn, user):
        school_id = self._default_school_id(conn, user)
        if not school_id:
            return self._json([])
        rows = db.q(conn, "SELECT * FROM packs WHERE school_id=? ORDER BY position, created_at", (school_id,))
        out = []
        for r in rows:
            titles = [x["title"] for x in db.q(conn, "SELECT c.title FROM pack_courses pc JOIN courses c ON c.id=pc.course_id WHERE pc.pack_id=? ORDER BY c.position", (r["id"],))]
            out.append({**db_row_to_dict(r), "course_titles": titles, "n_courses": len(titles)})
        return self._json(out)

    def _api_admin_pack_create(self, conn, user):
        body = self._body()
        school_id = user["school_id"]
        title = (body.get("title") or "").strip()
        if not school_id or not title:
            return self._json({"error": "titre obligatoire"}, code=400)
        slug = slugify(body.get("slug") or title)
        base, k = slug, 2
        while db.q1(conn, "SELECT id FROM packs WHERE school_id=? AND slug=?", (school_id, slug)):
            slug = f"{base}-{k}"; k += 1
        pid = db.new_id()
        db.ex(conn, """INSERT INTO packs (id, school_id, slug, title, subtitle, description_html, price, old_price, color_card, position, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
              (pid, school_id, slug, title, body.get("subtitle", ""), body.get("description_html", ""),
               body.get("price", 0), body.get("old_price"), body.get("color_card", ""),
               body.get("position", db.q1(conn, "SELECT COUNT(*) n FROM packs WHERE school_id=?", (school_id,))["n"]), db.now()))
        for cid in (body.get("course_ids") or []):
            db.ex(conn, "INSERT OR IGNORE INTO pack_courses (pack_id, course_id) VALUES (?,?)", (pid, cid))
        return self._json({"ok": True, "id": pid, "slug": slug}, code=201)

    def _api_admin_pack(self, conn, user, method, pack_id):
        p = db.q1(conn, "SELECT * FROM packs WHERE id=?", (pack_id,))
        if not p or not self._can_school(conn, user, p["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        if method == "PATCH":
            body = self._body()
            sets, vals = [], []
            for f in ("title", "subtitle", "description_html", "price", "old_price", "color_card", "position"):
                if f in body:
                    sets.append(f + "=?"); vals.append(body[f])
            if sets:
                vals.append(pack_id)
                db.ex(conn, "UPDATE packs SET " + ", ".join(sets) + " WHERE id=?", tuple(vals))
            return self._json({"ok": True})
        if method == "DELETE":
            db.ex(conn, "DELETE FROM packs WHERE id=?", (pack_id,))
            return self._json({"ok": True})
        return self._json({"error": "method_not_allowed"}, code=405)

    def _api_admin_pack_courses(self, conn, user, pack_id):
        p = db.q1(conn, "SELECT * FROM packs WHERE id=?", (pack_id,))
        if not p or not self._can_school(conn, user, p["school_id"]):
            return self._json({"error": "forbidden"}, code=403)
        body = self._body()
        for cid in (body.get("course_ids") or []):
            db.ex(conn, "INSERT OR IGNORE INTO pack_courses (pack_id, course_id) VALUES (?,?)", (pack_id, cid))
        for cid in (body.get("remove_course_ids") or []):
            db.ex(conn, "DELETE FROM pack_courses WHERE pack_id=? AND course_id=?", (pack_id, cid))
        return self._json({"ok": True})

    def _api_admin_leads(self, conn, user):
        school_id = self._default_school_id(conn, user)
        rows = db.q(conn, "SELECT * FROM leads WHERE school_id=? ORDER BY created_at DESC LIMIT 100", (school_id,))
        return self._json([db_row_to_dict(r) for r in rows])

    def _api_admin_school(self, conn, user):
        school = db.q1(conn, "SELECT * FROM schools WHERE id=?", (user["school_id"],))
        return self._json(db_row_to_dict(school) or {})

    def _api_admin_school_patch(self, conn, user):
        body = self._body()
        school = db.q1(conn, "SELECT * FROM schools WHERE id=?", (user["school_id"],))
        if not school and user["role"] == "superadmin":
            school = self._school_by_slug(conn, DEFAULT_SCHOOL_SLUG)
        if not school:
            return self._json({"error": "no_school"}, code=400)
        sets, vals = [], []
        for f in ("name", "accent", "tagline"):
            if f in body:
                sets.append(f + "=?"); vals.append(body[f])
        if sets:
            vals.append(school["id"])
            db.ex(conn, "UPDATE schools SET " + ", ".join(sets) + " WHERE id=?", tuple(vals))
        return self._json({"ok": True})

    # ==================================================================
    # API superadmin
    # ==================================================================
    def _api_super_schools(self, conn):
        rows = db.q(conn, "SELECT * FROM schools ORDER BY created_at")
        out = []
        for r in rows:
            out.append({**db_row_to_dict(r),
                        "courses": db.q1(conn, "SELECT COUNT(*) n FROM courses WHERE school_id=?", (r["id"],))["n"],
                        "students": db.q1(conn, "SELECT COUNT(*) n FROM users WHERE school_id=? AND role='student'", (r["id"],))["n"]})
        return self._json(out)

    def _api_super_school_create(self, conn):
        body = self._body()
        name = (body.get("name") or "").strip()
        if not name:
            return self._json({"error": "nom obligatoire"}, code=400)
        slug = slugify(body.get("slug") or name)
        base, k = slug, 2
        while self._school_by_slug(conn, slug):
            slug = f"{base}-{k}"; k += 1
        sid = db.new_id()
        db.ex(conn, "INSERT INTO schools (id, name, slug, accent, tagline, created_at) VALUES (?,?,?,?,?,?)",
              (sid, name, slug, body.get("accent", "sage"), body.get("tagline", ""), db.now()))
        return self._json({"ok": True, "id": sid, "slug": slug}, code=201)

    def _api_super_school_admin_create(self, conn, school_id):
        body = self._body()
        email = (body.get("email") or "").strip().lower()
        pw = body.get("password") or ""
        name = (body.get("name") or "").strip()
        if not email or "@" not in email or len(pw) < 6:
            return self._json({"error": "email / mot de passe invalide"}, code=400)
        school = db.q1(conn, "SELECT * FROM schools WHERE id=?", (school_id,))
        if not school:
            return self._json({"error": "école introuvable"}, code=404)
        if db.q1(conn, "SELECT id FROM users WHERE email=?", (email,)):
            return self._json({"error": "email déjà utilisé"}, code=409)
        uid = db.new_id()
        db.ex(conn, "INSERT INTO users (id, email, password_hash, name, role, school_id, created_at) VALUES (?,?,?,?,?,?,?)",
              (uid, email, auth.hash_password(pw), name or email.split("@")[0], "school_admin", school_id, db.now()))
        return self._json({"ok": True, "id": uid}, code=201)


# ==================================================================
# utils
# ==================================================================
def db_row_to_dict(r):
    if r is None:
        return None
    return {k: (v.decode("utf-8") if isinstance(v, bytes) else v) for k, v in dict(zip(r.keys(), tuple(r))).items()}


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[àâä]", "a", s); s = re.sub(r"[éèêë]", "e", s); s = re.sub(r"[îï]", "i", s)
    s = re.sub(r"[ôö]", "o", s); s = re.sub(r"[ùûü]", "u", s); s = re.sub(r"[ç]", "c", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "formation"


def main():
    os.makedirs(os.path.dirname(db.DB_PATH), exist_ok=True)
    db.init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"LMS Bien-Être v{VERSION} — http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()