/* app.js — LMS Bien-Être · SPA élève + admin v2.0 (fork Rosémary)
   Conventions : vanilla JS, esc() partout, node --check avant deploy.
   Règle apostrophes : toute chaîne JS contenant un ' français est en double quotes. */
"use strict";

/* ============================== utils ============================== */
var BOOT = { id: "", email: "", name: "", role: "student", school_id: null };
try { BOOT = JSON.parse(document.getElementById("boot-user").textContent); } catch (e) {}

var $ = function (s, c) { return (c || document).querySelector(s); };
var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
var esc = function (s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (m) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m];
  });
};

function toast(msg, isErr) {
  var root = $("#toast-root");
  if (!root) { return; }
  var t = document.createElement("div");
  t.className = "toast" + (isErr ? " err" : "");
  t.textContent = msg;
  root.appendChild(t);
  setTimeout(function () { t.remove(); }, 4200);
}

function api(path, opts) {
  opts = opts || {};
  var hasBody = Object.prototype.hasOwnProperty.call(opts, "body");
  var req = { method: hasBody ? "POST" : "GET", headers: {} };
  if (opts.method) { req.method = opts.method; }
  if (hasBody && req.method !== "GET" && req.method !== "DELETE") {
    req.body = JSON.stringify(opts.body === undefined ? {} : opts.body);
    req.headers["Content-Type"] = "application/json";
  }
  return fetch(path, req).then(function (r) {
    if (r.status === 401) { window.location.href = "/login"; throw new Error("unauthorized"); }
    return r.json();
  });
}

function money(v) {
  if (!v || v <= 0) { return "Gratuit"; }
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(v) + " €";
}

function fmtDate(iso) {
  if (!iso) { return ""; }
  return iso.slice(0, 10).split("-").reverse().join("/");
}

/* ============================== state ============================== */
var STATE = {
  me: null, school: null,
  myCourses: [], outline: null,
  currentCourse: null, currentLesson: null,
  adminCourse: null,
};

/* ============================== shell / nav ============================== */
function setView(name) {
  $$(".view").forEach(function (v) { v.classList.remove("on"); });
  var target = $("#view-" + name);
  if (target) { target.classList.add("on"); }
  $$("#side-nav a").forEach(function (a) { a.classList.toggle("on", a.dataset.view === name); });
}

function navClicks() {
  $$("#side-nav a").forEach(function (a) {
    a.addEventListener("click", function (ev) {
      ev.preventDefault();
      var v = a.dataset.view;
      setView(v);
      if (v === "dash") { renderDash(); }
      if (v === "ann") { renderAnnouncements(); }
      if (v === "admin") { initAdmin(); }
      if (v === "account") { renderAccount(); }
    });
  });
}

/* ============================== dash élève ============================== */
function renderDash() {
  api("/api/my/courses").then(function (courses) {
    STATE.myCourses = courses;
    var nDone = 0, nTotal = 0, nCerts = 0;
    courses.forEach(function (c) {
      nDone += c.done_lessons; nTotal += c.total_lessons;
      if (c.certificate_serial) { nCerts += 1; }
    });
    $("#k-courses").textContent = String(courses.length);
    $("#k-done").textContent = String(nDone);
    $("#k-pct").innerHTML = (nTotal ? Math.round(100 * nDone / nTotal) : 0) + "<span class='u'>%</span>";
    $("#k-certs").textContent = String(nCerts);

    var html = "";
    if (!courses.length) {
      html = '<div class="card center" style="padding:50px 30px">' +
        '<div style="font-size:40px">✦</div>' +
        '<h3 style="margin:12px 0 8px">Aucune formation pour le moment</h3>' +
        '<p class="muted" style="font-weight:300">Utilise le code premium reçu après achat ci-dessous, ou explore la <a href="/" style="color:var(--accent)">vitrine</a>.</p></div>';
    }
    courses.forEach(function (c) {
      var bar = '<div class="progress-track"><div class="progress-fill" style="width:' + c.progress_pct + '%"></div></div>';
      var cert = c.certificate_serial
        ? '<span class="badge badge-gold">🏅 Certifié — ' + esc(c.certificate_serial) + "</span>"
        : (c.total_lessons > 0 && c.done_lessons >= c.total_lessons && c.progress_pct >= 100
          ? '<button class="btn btn-accent btn-sm cert-btn" data-cert="' + esc(c.course_id) + '">🏅 Obtenir mon certificat</button>'
          : "");
      html += '<div class="card card-hover my-course mt-2" data-course="' + esc(c.course_id) + '">' +
        '<div class="th" style="--cc:' + esc(c.color_card || "#2DE28E") + '"></div>' +
        '<div class="bd"><h3>' + esc(c.title) + "</h3>" +
        '<div class="sub">' + esc(c.subtitle || "") + "</div>" +
        '<div class="pbar-line">' + bar + '<span class="pc">' + c.progress_pct + " % · " + c.done_lessons + "/" + c.total_lessons + "</span>" + cert + "</div>" +
        "</div></div>";
    });
    $("#dash-courses").innerHTML = html;
    $$("#dash-courses .my-course").forEach(function (el) {
      el.addEventListener("click", function () { openCourse(el.dataset.course); });
    });
    $$("#dash-courses .cert-btn").forEach(function (b) {
      b.addEventListener("click", function (ev) {
        ev.stopPropagation();
        tryCertificate(b.dataset.cert);
      });
    });
  }).catch(function () {});
  renderAnnouncements();
}

/* ============================== annonces ============================== */
function renderAnnouncements() {
  api("/api/my/announcements").then(function (rows) {
    var html = "";
    if (!rows.length) { html = '<p class="dimmer">Aucune annonce pour le moment.</p>'; }
    rows.forEach(function (a) {
      html += '<div class="card ann-card"><div class="dt">' + fmtDate(a.created_at) +
        (a.course_title ? " · " + esc(a.course_title) : "") + "</div><h3>" + esc(a.title) + "</h3>" +
        (a.body ? "<p>" + esc(a.body) + "</p>" : "") + "</div>";
    });
    $("#ann-list").innerHTML = html;
  }).catch(function () {});
}

/* ============================== course reader ============================== */
function openCourse(courseId) {
  api("/api/my/course/" + courseId).then(function (d) {
    STATE.currentCourse = d.course;
    STATE.outline = d.outline;
    renderOutline(d);
    $("#reader").classList.remove("hidden");
    document.body.style.overflow = "hidden";
    var first = null;
    d.outline.forEach(function (m) {
      if (first) { return; }
      m.lessons.forEach(function (l) {
        if (!first && !l.done && !l.locked) { first = l; }
      });
    });
    if (!first && d.outline.length && d.outline[0].lessons.length) { first = d.outline[0].lessons[0]; }
    if (first) { openLesson(first.id); } else { $("#lesson-wrap").innerHTML = '<p class="dimmer">Formation vide pour le moment.</p>'; }
  }).catch(function (e) {
    if (String(e && e.message).indexOf("not_enrolled") >= 0) { toast("Tu n'es pas inscrit à cette formation", true); }
  });
}

function closeReader() {
  $("#reader").classList.add("hidden");
  document.body.style.overflow = "";
  STATE.currentCourse = null; STATE.currentLesson = null;
  renderDash();
}
if ($("#reader-close")) { $("#reader-close").addEventListener("click", closeReader); }
if ($("#reader-back")) { $("#reader-back").addEventListener("click", closeReader); }

function renderOutline(d) {
  $("#reader-course-title").textContent = d.course.title;
  $("#reader-progress").style.width = d.progress_pct + "%";
  $("#reader-progress-lb").textContent = d.progress_pct + " % (" + d.done_lessons + "/" + d.total_lessons + ")";
  var html = "";
  d.outline.forEach(function (m) {
    html += '<div class="mod-head">' + esc(m.title) + "</div>";
    m.lessons.forEach(function (l) {
      var st = l.done ? '<span class="st done">✓</span>' : '<span class="st">○</span>';
      var lock = (l.locked && !l.done) ? " locked" : "";
      var icon = l.has_quiz ? " 🧩" : (l.has_video ? " 🎬" : (l.has_pdf ? " 📄" : ""));
      html += '<div class="lesson-item' + lock + '" data-lesson="' + esc(l.id) + '">' + st +
        '<span class="lt">' + esc(l.title) + icon + "</span></div>";
    });
  });
  $("#reader-outline").innerHTML = html;
  $$("#reader-outline .lesson-item").forEach(function (el) {
    el.addEventListener("click", function () {
      if (el.classList.contains("locked")) {
        toast("Leçon verrouillée — termine d'abord les précédentes (libération progressive)", true);
        return;
      }
      openLesson(el.dataset.lesson);
    });
  });
  markCur();
}

function markCur() {
  $$("#reader-outline .lesson-item").forEach(function (el) {
    el.classList.toggle("cur", el.dataset.lesson === STATE.currentLesson);
  });
}

function openLesson(id) {
  STATE.currentLesson = id;
  markCur();
  TIME_TICK.start(id);
  api("/api/lesson/" + id).then(function (d) {
    renderLesson(d);
    COACH.load(id);
    TIME_TICK.setMeta(d.lesson);
  }).catch(function () {
    $("#lesson-wrap").innerHTML = '<p class="dimmer">Contenu indisponible.</p>';
  });
}

/* ============== temps de visionnage actif (Qualiopi) ==============
   Tick POST /api/lesson/time toutes les 15 s UNIQUEMENT si l'onglet est
   visible (visibilitychange stoppe/envoie au retour). Sert aussi au
   blocage "marquer comme terminée" quand min_seconds est configuré. */
var TIME_TICK = {
  timer: null, lessonId: null, pending: 0, meta: null, MIN: 0,
  start: function (lessonId) {
    this.stop();
    this.lessonId = lessonId; this.pending = 0;
    var self = this;
    this.timer = setInterval(function () {
      if (document.visibilityState !== "visible") { return; }   // pause hors onglet
      self.pending += 15;
      if (self.pending >= 15) { self.flush(); }
    }, 15000);
    document.addEventListener("visibilitychange", function () {}, false);
  },
  stop: function () { if (this.timer) { clearInterval(this.timer); this.timer = null; } },
  setMeta: function (lesson) {
    // affichage du temps requis vs passé
    this.MIN = (lesson && lesson.min_seconds) || 0;
    var spent = (lesson && lesson.seconds_spent) || 0;
    this.paint(spent);
  },
  paint: function (spent) {
    var el = $("#reader-timer");
    if (!el) { return; }
    var s = spent || 0;
    if (this.MIN > 0) {
      el.textContent = "⏱ temps actif : " + Math.round(s / 60) + " min / " + Math.round(this.MIN / 60) + " min requis";
    } else {
      el.textContent = "⏱ temps actif : " + Math.round(s / 60) + " min";
    }
  },
  flush: function () {
    if (!this.lessonId || this.pending <= 0) { return; }
    var s = this.pending; this.pending = 0;
    var self = this;
    api("/api/lesson/time", { method: "POST", body: { lesson_id: this.lessonId, seconds: s } })
      .then(function () { self._last = (self._last || 0) + s; self.paint(self._last); })
      .catch(function () {});
  }
};

function ytEmbed(url) {
  var m = url.match(/(?:v=|youtu\.be\/|embed\/|shorts\/)([A-Za-z0-9_-]{6,})/);
  if (m) { return "https://www.youtube-nocookie.com/embed/" + m[1]; }
  return url;
}

function renderLesson(d) {
  var l = d.lesson;
  var videoBlock = "";
  if (l.video_url) {
    videoBlock = '<div class="video-box"><iframe src="' + esc(ytEmbed(l.video_url)) + '" allowfullscreen loading="lazy"></iframe></div>';
  } else {
    videoBlock = '<div class="video-box"><span style="font-size:30px">🎬</span>' +
      '<strong style="color:var(--text); font-weight:500">Vidéo à venir</strong>' +
      '<span style="font-size:12.5px">Une présentation vidéo sera ajoutée pour cette leçon.</span></div>';
  }
  var pdfBlock = l.pdf_url
    ? '<a class="pdf-link" href="' + esc(l.pdf_url) + '" target="_blank" rel="noopener">⬇️ Télécharger le support PDF — ' + esc(l.pdf_name || "support") + "</a>"
    : "";
  var navL = d.prev ? '<button class="btn btn-ghost btn-sm" data-nav="' + esc(d.prev.id) + '">← ' + esc(trunc(d.prev.title, 24)) + "</button>" : "";
  var navR = d.next ? '<button class="btn btn-ghost btn-sm" data-nav="' + esc(d.next.id) + '">' + esc(trunc(d.next.title, 24)) + " →</button>" : "";
  var doneBtn = l.done
    ? '<button class="btn btn-ghost btn-sm" id="btn-done">✓ Leçon terminée</button>'
    : '<button class="btn btn-white" id="btn-done">✓ Marquer comme terminée</button>';
  var quizBtn = d.quiz_id
    ? '<button class="btn btn-accent" id="btn-quiz">🧩 ' + esc(d.quiz_title) + " (min. " + d.quiz_pass_score + "%)</button>"
    : "";

  $("#lesson-wrap").innerHTML =
    '<div class="reader-crumb">' + esc(d.course.title) + "</div>" +
    "<h1>" + esc(l.title) + "</h1>" +
    (l.done ? '<div class="badge mt-1 mb-2">✓ Leçon terminée</div>' : "") +
    videoBlock +
    '<div class="lesson-content">' + (l.content_html || '<p class="dimmer">Contenu en préparation.</p>') + "</div>" +
    pdfBlock +
    '<div class="lesson-actions"><div class="row">' + navL + navR + "</div>" +
    '<div class="row">' + quizBtn + doneBtn + "</div></div>" +
    (d.quiz_id ? '<div class="mt-4" id="quiz-zone"></div>' : "");

  $$("#lesson-wrap [data-nav]").forEach(function (b) {
    b.addEventListener("click", function () { openLesson(b.dataset.nav); });
  });
  $("#btn-done").addEventListener("click", function () {
    api("/api/progress", { method: "POST", body: { lesson_id: l.id } }).then(function () {
      toast("Progression enregistrée ✓");
      refreshOutline();
      openLesson(l.id);
      maybeCertOffer();
    });
  });
  if (d.quiz_id) { $("#btn-quiz").addEventListener("click", function () { loadQuiz(d.quiz_id); }); }
  $("#coach-zone").innerHTML = '<p class="dimmer" style="font-size:12px">Espace coach — chargement…</p>';
  TIME_TICK._last = d.lesson.seconds_spent || 0;
  TIME_TICK.paint(d.lesson.seconds_spent || 0);
  window.scrollTo(0, 0);
}

/* ============== comments coach↔élève ============== */
var COACH = {
  load: function (lessonId) {
    api("/api/lesson/" + lessonId + "/comments").then(function (d) {
      var zone = $("#coach-zone");
      if (!zone) { return; }
      var html = '<div class="card coach-card"><div class="row" style="justify-content:space-between; margin-bottom:10px">' +
        "<strong>💬 Espace coach</strong>" +
        '<span class="pill-tag ' + (d.can_reply ? "acc" : "") + '">' + (d.can_reply ? "réponses ouvertes (coach)" : "privé — toi et ton coach") + "</span></div>";
      if (!d.comments.length) {
        html += '<p class="dimmer" style="font-size:13px">Aucun message encore — écris ci-dessous une question, ton coach te répond ici.</p>';
      }
      d.comments.forEach(function (c) {
        var isCoach = c.author_role === "coach";
        html += '<div class="coach-msg' + (isCoach ? " from-coach" : "") + '">' +
          '<div class="cm-head">' + (isCoach ? "🌿 " : "👤 ") + esc(c.author_name || c.author_email) +
          ' <span class="dimmer" style="font-size:11px">' + fmtDate(c.created_at) + "</span></div>" +
          '<div class="cm-body">' + esc(c.body) + "</div></div>";
      });
      html += '<div class="row mt-2" style="gap:8px"><input class="input" id="coach-input" placeholder="Écrire un message…">' +
        '<button class="btn btn-accent btn-sm" id="coach-send">Envoyer</button></div>';
      zone.innerHTML = html;
      $("#coach-send").addEventListener("click", function () {
        var txt = ($("#coach-input").value || "").trim();
        if (!txt) { return; }
        api("/api/lesson/" + lessonId + "/comments", { method: "POST", body: { body: txt } }).then(function () {
          COACH.load(lessonId);
        });
      });
      zone.dataset.loaded = "1";
    }).catch(function () { var z = $("#coach-zone"); if (z) { z.innerHTML = ""; } });
  }
};

function trunc(s, n) {
  s = String(s || "");
  if (s.length <= n) { return s; }
  return s.slice(0, n - 1) + "…";
}

function refreshOutline() {
  if (!STATE.currentCourse) { return; }
  api("/api/my/course/" + STATE.currentCourse.id).then(function (d) {
    STATE.outline = d.outline;
    renderOutline(d);
  });
}

function maybeCertOffer() {
  if (!STATE.currentCourse) { return; }
  api("/api/my/course/" + STATE.currentCourse.id).then(function (d) {
    if (!d.outline) { return; }
    var allDone = d.done_lessons >= d.total_lessons && d.total_lessons > 0;
    if (allDone && !d._fbAsked) {
      maybeFeedback(d);
    }
  }).catch(function () {});
  api("/api/certificate/" + STATE.currentCourse.id).then(function (d) {
    if (d && d.eligible && d.certificate) {
      showCert(d.certificate);
    }
  }).catch(function () {});
}

/* satisfaction à chaud : à 100 % on demande une note 1-5 + commentaire */
function maybeFeedback(courseData) {
  if (!STATE.currentCourse) { return; }
  var cid = STATE.currentCourse.id;
  // on ne propose qu'une fois par session de cours
  if (sessionStorage.getItem("fb_asked_" + cid)) { return; }
  sessionStorage.setItem("fb_asked_" + cid, "1");
  var stars = [1, 2, 3, 4, 5].map(function (n) {
    return '<button class="btn btn-ghost btn-sm fb-star" data-star="' + n + '">' + n + " ⭐</button>";
  }).join(" ");
  openModal('<h3>🌿 Ton avis compte</h3>' +
    '<p class="muted" style="font-size:13.5px; margin-bottom:16px">Tu as terminé la formation — comment s\'est passée ton expérience ?</p>' +
    '<div class="row" style="gap:8px; flex-wrap:wrap" id="fb-stars">' + stars + "</div>" +
    '<div class="mt-2"><span class="label">Un commentaire (optionnel)</span><textarea class="input" id="fb-comment" rows="3" placeholder="Ce qui t\'a le plus aidé…"></textarea></div>' +
    '<button class="btn btn-accent mt-2" id="fb-send">Envoyer mon avis</button>');
  var chosen = 5;
  $$(".fb-star").forEach(function (b) {
    b.addEventListener("click", function () { chosen = parseInt(b.dataset.star, 10); });
  });
  $("#fb-send").addEventListener("click", function () {
    api("/api/feedback", { method: "POST", body: { course_id: cid, rating: chosen, comment: $("#fb-comment").value } })
      .then(function () { closeModal(); toast("Merci pour ton avis 🌿"); });
  });
}

/* ============================== quiz ============================== */
function loadQuiz(quizId) {
  api("/api/my/quiz/" + quizId).then(function (d) {
    var zone = $("#quiz-zone");
    var html = '<h3 class="mt-3">🧩 ' + esc(d.quiz.title) + '</h3><p class="dimmer mb-2">' +
      d.questions.length + " question(s) · score requis : " + d.quiz.pass_score + "%</p>";
    d.questions.forEach(function (q, i) {
      html += '<div class="card quiz-q mt-2"><div class="qq">' + (i + 1) + ". " + esc(q.question) + "</div>";
      q.options.forEach(function (opt, oi) {
        html += '<label><input type="radio" name="q_' + esc(q.id) + '" value="' + oi + '"> ' + esc(opt) + "</label>";
      });
      html += "</div>";
    });
    html += '<button class="btn btn-accent mt-2" id="quiz-submit">Valider mes réponses</button><div id="quiz-result"></div>';
    zone.innerHTML = html;
    $("#quiz-submit").addEventListener("click", function () {
      var answers = {};
      var missing = false;
      d.questions.forEach(function (q) {
        var sel = $('input[name="q_' + q.id + '"]:checked');
        if (sel) { answers[q.id] = parseInt(sel.value, 10); } else { missing = true; }
      });
      if (missing) { toast("Réponds à toutes les questions", true); return; }
      $("#quiz-submit").disabled = true;
      api("/api/quiz/" + quizId + "/attempt", { method: "POST", body: { answers: answers } }).then(function (res) {
        var html2 = '<div class="card mt-3 center"><h3 class="' + (res.passed ? "quiz-result-ok" : "quiz-result-ko") + '">' +
          (res.passed ? "🎉 Réussi — " + res.pct + "%" : "Presque — " + res.pct + "% (requis " + d.quiz.pass_score + "%)") + "</h3>" +
          '<p class="dimmer" style="font-size:13px">' + res.score + "/" + res.max_score + " — reprends la leçon puis retente.</p></div>";
        res.results.forEach(function (r, i) {
          html2 += '<div class="quiz-q card mt-2"><div class="qq">' + (i + 1) + ". " + esc(r.question) + "</div>";
          r.options.forEach(function (opt, oi) {
            var style = "";
            if (oi === r.correct_index) { style = " style='color:var(--accent); font-weight:500'"; }
            if (oi === r.given && !r.ok) { style = " style='color:#F87171'"; }
            html2 += "<div" + style + ">" + (oi === r.correct_index ? "✓ " : (oi === r.given ? "✕ " : "· ")) + esc(opt) + "</div>";
          });
          html2 += '<div class="expl">💡 ' + esc(r.explanation || "") + "</div></div>";
        });
        $("#quiz-result").innerHTML = html2;
        $("#quiz-submit").disabled = false;
      });
    });
  });
}

/* ============================== certificat ============================== */
function tryCertificate(courseId) {
  api("/api/certificate/" + courseId).then(function (d) {
    if (d && d.eligible && d.certificate) { showCert(d.certificate); }
    else if (d) {
      var why = [];
      if (d.total && d.done < d.total) { why.push(d.done + "/" + d.total + " leçons terminées"); }
      if (d.quizzes_ok === false) { why.push("quiz non réussi(s)"); }
      toast("Pas encore éligible : " + (why.join(" · ") || "progression incomplète"), true);
    }
  });
}

function showCert(c) {
  openModal('<div class="cert-box"><div class="seal">🏅</div><h2>Certificat de réussite</h2>' +
    '<p style="font-size:17px; margin-top:14px"><strong>' + esc(c.student_name) + "</strong></p>" +
    '<p class="muted">a complété la formation</p>' +
    "<h3 style='color:var(--gold); margin-top:4px'>" + esc(c.course_title) + "</h3>" +
    '<p class="serial">N° ' + esc(c.serial) + " — " + fmtDate(c.issued_at) + "</p>" +
    '<button class="btn btn-white mt-4" onclick="window.print()">🖨️ Imprimer / PDF</button></div>');
}

/* ============================== modals ============================== */
function openModal(html) {
  $("#modal-content").innerHTML = html;
  $("#modal-root").classList.add("open");
  $$("#modal-root [data-close-modal]").forEach(function (el) { el.onclick = closeModal; });
}
function closeModal() { $("#modal-root").classList.remove("open"); }

/* ============================== account ============================== */
function renderAccount() {
  api("/api/me").then(function (d) {
    STATE.me = d.user; STATE.school = d.school;
    var roleLabel = d.user.role === "school_admin" ? "Administration d'école" : (d.user.role === "superadmin" ? "Superadmin CDB" : "Élève");
    $("#account-info").innerHTML =
      "<p><strong>" + esc(d.user.name || d.user.email) + "</strong> — " + roleLabel + "</p>" +
      "<p class='muted' style='font-size:13.5px'>" + esc(d.user.email) + (d.school ? " · École : " + esc(d.school.name) : "") + "</p>" +
      (d.is_admin ? "<p class='mt-2 muted' style='font-size:13px'>L'onglet Administration te donne accès au builder de formations, aux élèves, aux codes et aux leads.</p>" : "") +
      '<p class="mt-2 muted" style="font-size:13px">Membre depuis le ' + fmtDate(d.user.created_at) + "</p>";
  });
}

/* ============================== ADMIN ============================== */
var ATAB = "overview";

function initAdmin() {
  $$(".atab").forEach(function (b) {
    b.onclick = function () {
      $$(".atab").forEach(function (x) { x.classList.remove("on"); });
      b.classList.add("on");
      ATAB = b.dataset.atab;
      $$(".atab-view").forEach(function (v) { v.classList.add("hidden"); });
      $("#atab-" + ATAB).classList.remove("hidden");
      loadAtab(ATAB);
    };
  });
  loadAtab(ATAB);
}

function loadAtab(tab) {
  if (tab === "overview") { loadAdminOverview(); }
  if (tab === "courses") { loadAdminCourses(); }
  if (tab === "students") { loadAdminStudents(); }
  if (tab === "codes") { loadAdminCodes(); }
  if (tab === "packs") { loadAdminPacks(); }
  if (tab === "feedback") { loadAdminFeedback(); }
  if (tab === "leads") { loadAdminLeads(); }
  if (tab === "settings") { loadAdminSettings(); }
}

function loadAdminOverview() {
  api("/api/admin/overview").then(function (d) {
    $("#a-students").textContent = String(d.counts.students);
    $("#a-published").textContent = d.counts.published + "/" + d.counts.courses;
    $("#a-leads").textContent = String(d.counts.new_leads);
    $("#a-certs").textContent = String(d.counts.certificates);
    var bars = "";
    var keys = Object.keys(d.completion || {});
    if (!keys.length) { bars = "<p class='dimmer'>Aucune inscription pour l'instant.</p>"; }
    keys.forEach(function (k) {
      var pct = d.completion[k];
      bars += '<div class="cb"><div class="top"><span>' + esc(k) + "</span><span class='pc'>" + pct + " %</span></div>" +
        '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div></div>';
    });
    $("#a-completion").innerHTML = bars;
    var rec = "";
    (d.recent_enrollments || []).forEach(function (r) {
      rec += '<div class="row" style="justify-content:space-between; padding:9px 0; border-bottom:1px solid var(--border)">' +
        "<span><strong>" + esc(r.name || r.email) + "</strong> <span class='dimmer'>→ " + esc(r.course_title) + "</span></span>" +
        "<span class='dimmer' style='font-size:12px'>" + fmtDate(r.enrolled_at) + "</span></div>";
    });
    $("#a-recent").innerHTML = rec || "<p class='dimmer'>–</p>";
  });
}

function loadAdminCourses() {
  api("/api/admin/courses").then(function (rows) {
    var html = "";
    if (!rows.length) { html = "<p class='dimmer'>Aucune formation — crée la première avec « + Nouvelle formation ».</p>"; }
    rows.forEach(function (c) {
      var tags = "<span class='pill-tag " + (c.status === "published" ? "acc" : "") + "'>" + (c.status === "published" ? "publiée" : "brouillon") + "</span> " +
        "<span class='pill_tag'>" + esc(c.level) + "</span>" +
        (c.price ? " <span class='pill-tag gold'>" + money(c.price) + "</span>" : "");
      html += '<div class="card card-hover mt-2" style="cursor:pointer" data-course="' + esc(c.id) + '">' +
        '<div class="row" style="gap:14px">' +
        '<span style="width:70px; height:52px; border-radius:12px; flex:none; background:linear-gradient(135deg,' + esc(c.color_card || "#2DE28E") + ', transparent 140%)"></span>' +
        '<div style="flex:1"><strong>' + esc(c.title) + "</strong><br>" + tags + "</div>" +
        "<div class='dimmer' style='font-size:12.5px'>" + c.modules + " modules · " + c.lessons + " leçons</div>" +
        "</div></div>";
    });
    $("#admin-courses").innerHTML = html;
    $$("#admin-courses [data-course]").forEach(function (el) {
      el.addEventListener("click", function () { openCourseBuilder(el.dataset.course); });
    });
  });
}

function newCourseModal() {
  openModal('<h3>Nouvelle formation</h3><p class="muted" style="font-size:13.5px; margin-bottom:16px">Elle naît en brouillon : complète la fiche puis publie-la.</p>' +
    '<div style="display:flex; flex-direction:column; gap:12px">' +
    '<div><span class="label">Titre</span><input class="input" id="nc-title"></div>' +
    '<div><span class="label">Sous-titre (promesse en une ligne)</span><input class="input" id="nc-sub"></div>' +
    '<div><span class="label">Niveau</span><select class="input" id="nc-level"><option>débutant</option><option>intermédiaire</option><option>expert</option></select></div>' +
    '<div class="grid-2"><div><span class="label">Prix (€)</span><input class="input" id="nc-price" type="number" value="97"></div>' +
    '<div><span class="label">Ancien prix (barré, optionnel)</span><input class="input" id="nc-old" type="number"></div></div>' +
    '<div><span class="label">Durée affichée</span><input class="input" id="nc-dur"></div>' +
    '<div><span class="label">Couleur de vignette</span><input class="input" id="nc-color" type="color" value="#2DE28E" style="height:44px; padding:4px"></div>' +
    '<div><span class="label">Description longue (HTML autorisé)</span><textarea id="nc-desc" class="input rich-editor" rows="4"></textarea></div>' +
    '<button class="btn btn-accent" id="nc-save">Créer la formation</button></div>');
  $("#nc-save").addEventListener("click", function () {
    var old = $("#nc-old").value;
    api("/api/admin/courses", {
      method: "POST",
      body: {
        title: $("#nc-title").value, subtitle: $("#nc-sub").value, level: $("#nc-level").value,
        price: parseFloat($("#nc-price").value || "0"),
        old_price: old ? parseFloat(old) : null,
        duration_hours: $("#nc-dur").value, color_card: $("#nc-color").value,
        description_html: $("#nc-desc").value,
      },
    }).then(function (r) {
      if (r.ok) { closeModal(); toast("Formation créée ✓"); loadAdminCourses(); }
      else { toast(r.error || "Erreur", true); }
    });
  });
}

function openCourseBuilder(courseId) {
  api("/api/admin/course/" + courseId).then(function (d) {
    STATE.adminCourse = d;
    var c = d.course;
    var modList = d.outline || [];
    $("#admin-courses").innerHTML =
      '<button class="btn btn-ghost btn-sm mb-3" id="cb-back">← Toutes les formations</button>' +
      '<div class="row mb-3" style="gap:14px; flex-wrap:wrap">' +
      "<h2 style='font-size:21px'>" + esc(c.title) + "</h2>" +
      "<span class='pill-tag " + (c.status === "published" ? "acc" : "") + "'>" + (c.status === "published" ? "publiée" : "brouillon") + "</span>" +
      "<span class='pill_tag'>" + esc(c.level) + "</span>" +
      "<span class='pill-tag gold'>" + money(c.price) + "</span>" +
      '<div class="spacer"></div>' +
      '<button class="btn btn-white btn-sm" id="cb-publish">' + (c.status === "published" ? "Dépublier" : "🚀 Publier") + "</button>" +
      '<button class="btn btn-danger btn-sm" id="cb-delete">Supprimer</button></div>' +
      '<div class="card mb-3"><div class="grid-2">' +
      '<div><span class="label">Titre</span><input class="input" id="ed-title" value="' + esc(c.title) + '"></div>' +
      '<div><span class="label">Sous-titre</span><input class="input" id="ed-sub" value="' + esc(c.subtitle || "") + '"></div>' +
      '<div><span class="label">Prix (€)</span><input class="input" id="ed-price" type="number" value="' + (c.price || 0) + '"></div>' +
      '<div><span class="label">Durée affichée</span><input class="input" id="ed-dur" value="' + esc(c.duration_hours || "") + '"></div>' +
      "</div>" +
      '<div class="mt-2"><span class="label">Description longue (HTML)</span><textarea id="ed-desc" class="input rich-editor" rows="4">' + esc(c.description_html || "") + "</textarea></div>" +
      '<button class="btn btn-white btn-sm mt-2" id="ed-save">💾 Enregistrer la fiche</button></div>' +
      '<div class="row mb-2"><h3>Modules &amp; leçons</h3><div class="spacer"></div><button class="btn btn-accent btn-sm" id="add-mod">+ Module</button></div>' +
      '<div id="mod-list"></div>';

    $("#cb-back").addEventListener("click", loadAdminCourses);
    $("#ed-save").addEventListener("click", saveCourseForm);
    $("#cb-publish").addEventListener("click", function () {
      var pub = c.status !== "published";
      api("/api/admin/course/" + courseId, { method: "PATCH", body: { status: pub ? "published" : "draft" } }).then(function () {
        toast(pub ? "Formation publiée 🚀" : "Formation dépubliée");
        openCourseBuilder(courseId);
      });
    });
    $("#cb-delete").addEventListener("click", function () {
      if (!window.confirm("Supprimer la formation et TOUS ses modules/leçons ?")) { return; }
      api("/api/admin/course/" + courseId, { method: "DELETE", body: {} }).then(function () {
        toast("Formation supprimée");
        loadAdminCourses();
      });
    });
    $("#add-mod").addEventListener("click", function () { addModuleModal(courseId); });

    var modsHtml = "";
    if (!modList.length) { modsHtml = "<p class='dimmer'>Aucun module — ajoute le premier pour structurer la formation.</p>"; }
    modList.forEach(function (m) {
      modsHtml += '<div class="card mt-2"><div class="row" style="justify-content:space-between">' +
        "<strong>" + esc(m.title) + "</strong><div class='spacer'></div>" +
        "<button class='btn btn-ghost btn-sm' data-addlesson=\"" + esc(m.id) + '">+ Leçon</button>' +
        "<button class='btn btn-danger btn-sm' data-delmod=\"" + esc(m.id) + '">✕</button></div>' +
        '<p class="dimmer" style="font-size:12.5px; margin-top:6px">' + esc(m.description || "") + "</p>";
      (m.lessons || []).forEach(function (l) {
        var tags = (l.has_video ? "<span class='pill-tag acc'>🎬</span>" : "") +
          (l.has_pdf ? "<span class='pill_tag'>PDF</span>" : "") +
          (l.has_quiz ? "<span class='pill-tag gold'>🧩 quiz</span>" : "") +
          (l.free_preview ? "<span class='pill-tag acc'>extrait gratuit</span>" : "") +
          (l.drip ? "<span class='pill-tag'>drip J+" + l.drip + "</span>" : "");
        modsHtml += '<div class="lesson-line" data-lesson="' + esc(l.id) + '">· ' + esc(l.title) + " " + tags + "</div>";
      });
      modsHtml += "</div>";
    });
    $("#mod-list").innerHTML = modsHtml;
    $$("#mod-list [data-addlesson]").forEach(function (b) {
      b.addEventListener("click", function (e) { e.stopPropagation(); addLessonModal(b.dataset.addlesson, courseId); });
    });
    $$("#mod-list [data-delmod]").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        if (!window.confirm("Supprimer ce module et toutes ses leçons ?")) { return; }
        api("/api/admin/module/" + b.dataset.delmod, { method: "DELETE", body: {} }).then(function () {
          toast("Module supprimé");
          openCourseBuilder(courseId);
        });
      });
    });
    $$("#mod-list [data-lesson]").forEach(function (b) {
      b.addEventListener("click", function () { openLessonEditor(b.dataset.lesson, courseId); });
    });
  });
}

function saveCourseForm() {
  var c = STATE.adminCourse.course;
  api("/api/admin/course/" + c.id, {
    method: "PATCH",
    body: {
      title: $("#ed-title").value, subtitle: $("#ed-sub").value,
      price: parseFloat($("#ed-price").value || "0"),
      duration_hours: $("#ed-dur").value,
      description_html: $("#ed-desc").value,
    },
  }).then(function () { toast("Fiche enregistrée ✓"); });
}

function addModuleModal(courseId) {
  openModal('<h3>Nouveau module</h3><div style="display:flex; flex-direction:column; gap:12px; margin-top:14px">' +
    '<div><span class="label">Titre du module</span><input class="input" id="nm-title"></div>' +
    '<div><span class="label">Description</span><textarea class="input" id="nm-desc" rows="2"></textarea></div>' +
    '<button class="btn btn-accent" id="nm-save">Ajouter</button></div>');
  $("#nm-save").addEventListener("click", function () {
    api("/api/admin/course/" + courseId + "/module", {
      method: "POST",
      body: { title: $("#nm-title").value, description: $("#nm-desc").value },
    }).then(function (r) {
      if (r.ok) { closeModal(); toast("Module ajouté ✓"); openCourseBuilder(courseId); }
      else { toast(r.error || "Erreur", true); }
    });
  });
}

function addLessonModal(moduleId, courseId) {
  openModal('<h3>Nouvelle leçon</h3><div style="display:flex; flex-direction:column; gap:12px; margin-top:14px">' +
    '<div><span class="label">Titre de la leçon</span><input class="input" id="nl-title"></div>' +
    '<div><span class="label">Contenu (HTML)</span><textarea class="input rich-editor" id="nl-content" rows="5"></textarea></div>' +
    '<div><span class="label">URL vidéo (optionnel — YouTube, Vimeo, chemin /assets/…)</span><input class="input" id="nl-video"></div>' +
    '<div class="grid-2"><div><span class="label">Extrait gratuit (aperçu public)</span><select class="input" id="nl-free"><option value="">Non</option><option value="1">Oui</option></select></div>' +
    '<div><span class="label">Drip — libération J+n de leçons terminées</span><input class="input" id="nl-drip" type="number" value="0"></div></div>' +
    '<button class="btn btn-accent" id="nl-save">Ajouter</button></div>');
  $("#nl-save").addEventListener("click", function () {
    api("/api/admin/module/" + moduleId + "/lesson", {
      method: "POST",
      body: {
        title: $("#nl-title").value, content_html: $("#nl-content").value,
        video_url: $("#nl-video").value,
        free_preview: $("#nl-free").value === "1",
        drip_days: parseInt($("#nl-drip").value || "0", 10),
      },
    }).then(function (r) {
      if (r.ok) { closeModal(); toast("Leçon ajoutée ✓"); openCourseBuilder(courseId); }
      else { toast(r.error || "Erreur", true); }
    });
  });
}

function openLessonEditor(lessonId, courseId) {
  api("/api/admin/lesson/" + lessonId).then(function (d) {
    var l = d.lesson;
    var q = d.quiz;
    var quizBlock = "";
    if (q) {
      quizBlock = '<div class="card mt-2" style="background:var(--bg-3)"><div class="row" style="justify-content:space-between"><strong>🧩 Quiz — ' + esc(q.title) + " (" + q.questions.length + " questions, min. " + q.pass_score + "%)</strong>" +
        '<button class="btn btn-danger btn-sm" id="le-quiz-del">Retirer le quiz</button></div></div>';
    }
    openModal('<h3>Éditer la leçon</h3><div style="display:flex; flex-direction:column; gap:12px; margin-top:14px">' +
      '<div><span class="label">Titre</span><input class="input" id="le-title" value="' + esc(l.title) + '"></div>' +
      '<div><span class="label">Contenu (HTML)</span><textarea class="input rich-editor" id="le-content" rows="7">' + esc(l.content_html || "") + "</textarea></div>" +
      '<div><span class="label">URL vidéo</span><input class="input" id="le-video" value="' + esc(l.video_url || "") + '"></div>' +
      '<div class="grid-3"><div><span class="label">Extrait gratuit</span><select class="input" id="le-free"><option value="">Non</option><option value="1"' + (l.free_preview ? " selected" : "") + '>Oui</option></select></div>' +
      '<div><span class="label">Drip J+</span><input class="input" id="le-drip" type="number" value="' + (l.drip_days || 0) + '"></div>' +
      '<div><span class="label">Position</span><input class="input" id="le-pos" type="number" value="' + (l.position || 0) + '"></div></div>' +
      (l.pdf_name ? "<p style='font-size:13px'>PDF attaché : <strong>" + esc(l.pdf_name) + "</strong> <button class='btn btn-ghost btn-sm' id='le-pdf-del'>retirer</button></p>" : "") +
      '<div><span class="label">Joindre un PDF (max 12 Mo)</span><input class="input" id="le-pdf" type="file" accept="application/pdf"></div>' +
      quizBlock +
      '<button class="btn btn-white" id="le-save">💾 Enregistrer</button>' +
      '<button class="btn btn-danger" id="le-del">Supprimer la leçon</button></div>');
    $("#le-save").addEventListener("click", function () {
      api("/api/admin/lesson/" + lessonId, {
        method: "PATCH",
        body: {
          title: $("#le-title").value, content_html: $("#le-content").value,
          video_url: $("#le-video").value, free_preview: $("#le-free").value === "1",
          drip_days: parseInt($("#le-drip").value || "0", 10),
          position: parseInt($("#le-pos").value || "0", 10),
        },
      }).then(function () { toast("Leçon enregistrée ✓"); closeModal(); openCourseBuilder(courseId); });
      var f = $("#le-pdf").files && $("#le-pdf").files[0];
      if (f) {
        var reader = new FileReader();
        reader.onload = function () {
          var b64 = String(reader.result).split(",")[1];
          api("/api/admin/lesson/" + lessonId + "/pdf", {
            method: "POST",
            body: { b64: b64, name: f.name },
          }).then(function (r) {
            toast(r.ok ? "PDF joint ✓ (" + Math.round((r.bytes || 0) / 1024) + " Ko)" : (r.error || "Erreur PDF"), !r.ok);
          });
        };
        reader.readAsDataURL(f);
      }
    });
    var pdel = $("#le-pdf-del");
    if (pdel) { pdel.addEventListener("click", function () {
      api("/api/admin/lesson/" + lessonId, { method: "PATCH", body: { pdf_name: "" } }).then(function () { toast("PDF retiré"); closeModal(); openCourseBuilder(courseId); });
    }); }
    var qdel = $("#le-quiz-del");
    if (qdel) { qdel.addEventListener("click", function () {
      api("/api/admin/lesson/" + lessonId, { method: "PATCH", body: { quiz: null } }).then(function () { toast("Quiz retiré"); closeModal(); openCourseBuilder(courseId); });
    }); }
    $("#le-del").addEventListener("click", function () {
      if (!window.confirm("Supprimer cette leçon ?")) { return; }
      api("/api/admin/lesson/" + lessonId, { method: "DELETE", body: {} }).then(function () {
        closeModal(); toast("Leçon supprimée");
        openCourseBuilder(courseId);
      });
    });
  });
}

function loadAdminStudents() {
  api("/api/admin/students").then(function (rows) {
    var html = "";
    if (!rows.length) { html = "<p class='dimmer'>Aucun élève pour l'instant — les inscriptions arrivent par code ou via « + Inscrire ».</p>"; }
    rows.forEach(function (s) {
      var initial = String(s.name || s.email).charAt(0).toUpperCase();
      var tags = String(s.tags || "").split(",").filter(function (t) { return t.trim(); }).map(function (t) {
        return "<span class='pill-tag'>" + esc(t.trim()) + "</span>";
      }).join(" ");
      var enr = (s.enrollments || []).map(function (e) {
        return "<div style='margin:4px 0 0 52px; font-size:12.5px'>" + esc(e.title) +
          " — <span style='color:var(--accent); font-weight:500'>" + e.pct + " %</span>" +
          (e.status === "completed" ? " 🏅" : "") +
          (e.pct >= 80 && e.status !== "completed" ? "<button class='btn btn-ghost btn-sm' style='padding:2px 9px; font-size:11px; margin-left:8px' data-attend='" + esc(e.course_id) + "' data-user='" + esc(s.id) + "'>📜 Attestation assiduité</button>" : "") +
          "<button class='btn btn-danger btn-sm' style='padding:2px 9px; font-size:11px; margin-left:8px' data-unenroll=\"" + esc(e.enroll_id) + '\">✕</button></div>';
      }).join("");
      s._tagsHtml = tags;
      html += '<div class="card mt-2"><div class="row" style="gap:14px">' +
        '<div style="width:40px; height:40px; border-radius:50%; background:var(--bg-3); flex:none; display:flex; align-items:center; justify-content:center; color:var(--accent); font-weight:600">' + esc(initial) + "</div>" +
        '<div style="flex:1"><strong>' + esc(s.name || s.email) + "</strong> <span class='dimmer' style='font-size:12.5px'>" + esc(s.email) + "</span> " + (s._tagsHtml || "") + "<br>" +
        "<span class='dimmer' style='font-size:12px'>depuis le " + fmtDate(s.created_at) + " · " + s.n_courses + " formation(s) · " + (s.n_completed || 0) + " terminée(s)</span>" +
        "<button class='btn btn-ghost btn-sm' style='padding:2px 10px; font-size:11px; margin-left:10px' data-tags='" + esc(s.id) + "' data-cur='" + esc(s.tags || "") + "'>🏷 Tag</button></div></div>" + enr + "</div>";
    });
    $("#admin-students").innerHTML = html;
    $$("#admin-students [data-unenroll]").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        if (!window.confirm("Désinscrire cet élève de cette formation ?")) { return; }
        api("/api/admin/enrollment/" + b.dataset.unenroll, { method: "DELETE", body: {} }).then(loadAdminStudents);
      });
    });
    $$("#admin-students [data-attend]").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        api("/api/admin/attendance/" + b.dataset.user, { method: "POST", body: { course_id: b.dataset.attend } }).then(function (r) {
          if (r.ok) { toast(r.already ? "Attestation déjà délivrée" : "Attestation délivrée : " + (r.serial || "")); loadAdminStudents(); }
          else { toast(r.error || "Erreur", true); }
        });
      });
    });
    $$("#admin-students [data-tags]").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        var uid = b.dataset.tags;
        openModal('<h3>🏷 Tags élève</h3>' +
          '<p class="muted" style="font-size:13px; margin-bottom:14px">Sépare les tags par des virgules — ex : vip, suivi-6-mois, atelier-janvier</p>' +
          '<input class="input" id="tg-input" value="' + esc(b.dataset.cur) + '">' +
          '<button class="btn btn-accent mt-2" id="tg-save">Enregistrer</button>');
        $("#tg-save").addEventListener("click", function () {
          api("/api/admin/students", { method: "PATCH", body: { user_id: uid, tags: $("#tg-input").value } }).then(function () {
            closeModal(); toast("Tags enregistrés ✓"); loadAdminStudents();
          });
        });
      });
    });
  });
}

function enrollModal() {
  Promise.all([api("/api/admin/students"), api("/api/admin/courses")]).then(function (rs) {
    var students = rs[0] || [];
    var courses = rs[1] || [];
    if (!students.length || !courses.length) { toast("Il faut au moins un élève et une formation", true); return; }
    var oS = students.map(function (s) { return '<option value="' + esc(s.id) + '">' + esc(s.name || s.email) + "</option>"; }).join("");
    var oC = courses.map(function (c) { return '<option value="' + esc(c.id) + '">' + esc(c.title) + "</option>"; }).join("");
    openModal('<h3>Inscrire un élève</h3><div style="display:flex; flex-direction:column; gap:12px; margin-top:14px">' +
      '<div><span class="label">Élève</span><select class="input" id="en-student">' + oS + "</select></div>" +
      '<div><span class="label">Formation</span><select class="input" id="en-course">' + oC + "</select></div>" +
      '<button class="btn btn-accent" id="en-save">Inscrire</button></div>');
    $("#en-save").addEventListener("click", function () {
      api("/api/admin/enroll", { method: "POST", body: { user_id: $("#en-student").value, course_id: $("#en-course").value } }).then(function (r) {
        if (r.ok) { closeModal(); toast("Élève inscrit ✓"); loadAdminStudents(); } else { toast(r.error || "Erreur", true); }
      });
    });
  });
}

function loadAdminCodes() {
  api("/api/admin/codes").then(function (rows) {
    var chips = (rows || []).map(function (cd) {
      return '<span class="code-chip ' + (cd.status === "used" ? "used" : "") + '">' + esc(cd.code) +
        "<span class='dimmer' style='text-decoration:none; font-size:11px'>" + esc(cd.course_title || "—") + (cd.status === "revoked" ? " · révoqué" : (cd.status === "used" ? " · utilisé" : "")) +
        "</span>" + (cd.status === "active" ? "<button class='btn btn-danger btn-sm' style='padding:2px 8px; font-size:11px' data-revoke=\"" + esc(cd.id) + '">✕</button>' : "") +
        "</span>";
    }).join("");
    $("#admin-codes").innerHTML =
      '<div class="code-list">' + (chips || "<p class='dimmer'>Aucun code — génère le premier lot.</p>") + "</div>";
    $$("#admin-codes [data-revoke]").forEach(function (b) {
      b.addEventListener("click", function () {
        api("/api/admin/code/" + b.dataset.revoke, { method: "DELETE", body: {} }).then(loadAdminCodes);
      });
    });
  });
}

function newCodesModal() {
  Promise.all([api("/api/admin/courses"), api("/api/admin/packs")]).then(function (rs) {
    var courses = rs[0] || [];
    var packs = rs[1] || [];
    var oP = (packs || []).map(function (p) { return '<option data-kind="pack" value="' + esc(p.id) + '">📦 PACK — ' + esc(p.title) + "</option>"; }).join("");
    var oC = '<option value="">— une seule formation —</option>' +
      (courses || []).map(function (c) { return '<option value="' + esc(c.id) + '">' + esc(c.title) + "</option>"; }).join("");
    openModal('<h3>Générer des codes d\'accès</h3><div style="display:flex; flex-direction:column; gap:12px; margin-top:14px">' +
      '<div><span class="label">Cible du code</span><select class="input" id="gc-target">' + oP + oC + "</select></div>" +
      '<div><span class="label">Quantité (1 à 50)</span><input class="input" id="gc-count" type="number" value="1" min="1" max="50"></div>' +
      '<div><span class="label">Note interne</span><input class="input" id="gc-note" placeholder="ex : Client Marie D. — vente 01/10"></div>' +
      '<button class="btn btn-accent" id="gc-save">Générer</button></div>');
    $("#gc-save").addEventListener("click", function () {
      var sel = $("#gc-target");
      var opt = sel.options[sel.selectedIndex];
      var isPack = opt && opt.dataset.kind === "pack";
      var bodyC = { count: parseInt($("#gc-count").value || "1", 10), note: $("#gc-note").value };
      if (isPack) { bodyC.pack_id = sel.value; } else { bodyC.course_id = sel.value || null; }
      api("/api/admin/codes", {
        method: "POST",
        body: bodyC,
      }).then(function (r) {
        if (r.ok) {
          openModal("<h3>Codes générés ✓</h3><p class='muted' style='font-size:13.5px'>Copie-les et envoie-les à tes élèves — un code = une activation :</p>" +
            '<div class="code-list mt-2">' + (r.codes || []).map(function (cd) {
              return '<span class="code-chip" style="user-select:all">' + esc(cd) + "</span>";
            }).join("") + "</div>");
          loadAdminCodes();
        } else { toast(r.error || "Erreur", true); }
      });
    });
  });
}

/* ============== admin packs ============== */
function loadAdminPacks() {
  Promise.all([api("/api/admin/packs"), api("/api/admin/courses")]).then(function (rs) {
    var packs = rs[0] || [];
    var courses = rs[1] || [];
    var html = "";
    if (!packs.length) { html = "<p class='dimmer'>Aucun pack — un pack = 1 seul code qui débloque plusieurs formations.</p>"; }
    packs.forEach(function (pk) {
      html += '<div class="card mt-2"><div class="row" style="justify-content:space-between">' +
        "<div style='flex:1'><strong>📦 " + esc(pk.title) + "</strong> <span class='pill-tag gold'>" + money(pk.price) + "</span>" +
        "<p class='dimmer' style='font-size:12.5px; margin-top:4px'>" + esc(pk.subtitle || "") + "</p>" +
        "<p style='font-size:13px'>Contenu : " + (pk.course_titles || []).map(function (t) { return "<span class='pill-tag acc'>" + esc(t) + "</span>"; }).join(" ") + "</p></div>" +
        "<button class='btn btn-danger btn-sm' data-delpack='" + esc(pk.id) + "'>✕</button></div></div>";
    });
    $("#admin-packs").innerHTML = html;
    $$("#admin-packs [data-delpack]").forEach(function (b) {
      b.addEventListener("click", function () {
        if (!window.confirm("Supprimer ce pack ? (les codes pack déjà générés ne fonctionneront plus)")) { return; }
        api("/api/admin/pack/" + b.dataset.delpack, { method: "DELETE", body: {} }).then(loadAdminPacks);
      });
    });
    STATE._coursesForPack = courses;
  });
}

function newPackModal() {
  var courses = STATE._coursesForPack || [];
  if (!courses.length) { toast("Crée d'abord une formation", true); return; }
  var checks = courses.map(function (c) {
    return '<label style="display:flex; gap:8px; align-items:center; padding:8px 0"><input type="checkbox" class="pk-course" value="' + esc(c.id) + '"> ' + esc(c.title) + "</label>";
  }).join("");
  openModal('<h3>Nouveau pack</h3><p class="muted" style="font-size:13px; margin-bottom:14px">Un code généré pour ce pack inscrit l\'élève à TOUTES les formations cochées.</p>' +
    '<div style="display:flex; flex-direction:column; gap:12px">' +
    '<div><span class="label">Titre</span><input class="input" id="pk-title" value="Accompagnement complet"></div>' +
    '<div><span class="label">Sous-titre</span><input class="input" id="pk-sub" placeholder="Ce que couvre le pack"></div>' +
    '<div class="grid-2"><div><span class="label">Prix affiché (€)</span><input class="input" id="pk-price" type="number" value="997"></div>' +
    '<div><span class="label">Ancien prix (barré)</span><input class="input" id="pk-old" type="number"></div></div>' +
    '<div><span class="label">Formations du pack</span><div style="border:1px solid var(--border); border-radius:12px; padding:6px 14px">' + checks + "</div></div>" +
    '<button class="btn btn-accent" id="pk-save">Créer le pack</button></div>');
  $("#pk-save").addEventListener("click", function () {
    var ids = $$(".pk-course").filter(function (x) { return x.checked; }).map(function (x) { return x.value; });
    if (!ids.length) { toast("Coche au moins une formation", true); return; }
    api("/api/admin/packs", {
      method: "POST",
      body: { title: $("#pk-title").value, subtitle: $("#pk-sub").value,
              price: parseFloat($("#pk-price").value || "0"),
              old_price: $("#pk-old").value ? parseFloat($("#pk-old").value) : null,
              course_ids: ids },
    }).then(function (r) {
      if (r.ok) { closeModal(); toast("Pack créé ✓ — génère maintenant un code pack"); loadAdminPacks(); }
      else { toast(r.error || "Erreur", true); }
    });
  });
}

/* ============== admin feedback (satisfaction à chaud) ============== */
function loadAdminFeedback() {
  api("/api/admin/feedback").then(function (rows) {
    var html = "";
    if (!rows.length) { html = "<p class='dimmer'>Aucun avis — la note est proposée à l'élève quand il atteint 100 % de complétion.</p>"; }
    var avg = rows.length ? Math.round(10 * rows.reduce(function (a, r) { return a + (r.rating || 0); }, 0) / rows.length) / 10 : 0;
    if (rows.length) {
      html += '<div class="card mb-2 center"><span class="stat-giant" style="font-size:38px">' + avg + '<span class="unit">/5</span></span>' +
        "<p class='dimmer' style='font-size:12px'>moyenne sur " + rows.length + " avis</p></div>";
    }
    rows.forEach(function (f) {
      html += '<div class="card mt-2"><div class="row" style="justify-content:space-between">' +
        "<strong>" + esc(f.student_name || "—") + " <span class='dimmer' style='font-weight:400; font-size:12.5px'>· " + esc(f.course_title || "") + "</span></strong>" +
        "<span class='pill-tag gold'>" + "⭐".repeat(Math.round(f.rating || 0)) + "</span></div>" +
        (f.comment ? "<p class='muted' style='font-size:13.5px; margin-top:8px'>" + esc(f.comment) + "</p>" : "") +
        "<div class='dimmer' style='font-size:11.5px'>" + fmtDate(f.created_at) + "</div></div>";
    });
    $("#admin-feedback").innerHTML = html;
  });
}

function loadAdminLeads() {
  api("/api/admin/leads").then(function (rows) {
    var html = "";
    if (!rows.length) { html = "<p class='dimmer'>Aucun lead — chaque visiteur qui laisse son email sur la vitrine apparaîtra ici.</p>"; }
    rows.forEach(function (l) {
      html += '<div class="card mt-2"><div class="row" style="justify-content:space-between">' +
        "<div><strong>" + esc(l.name || l.email) + "</strong> <span class='dimmer' style='font-size:12.5px'>" + esc(l.email) + "</span></div>" +
        "<span class='pill-tag acc'>nouveau</span></div>" +
        (l.goal ? "<p class='muted' style='font-size:13px; margin-top:8px'>" + esc(l.goal) + "</p>" : "") +
        "<div class='dt' style='font-size:11.5px; color:var(--text-3)'>" + fmtDate(l.created_at) + "</div></div>";
    });
    $("#admin-leads").innerHTML = html;
  });
}

function loadAdminSettings() {
  api("/api/admin/school").then(function (s) {
    $("#set-name").value = s.name || "";
    $("#set-tagline").value = s.tagline || "";
    $("#set-accent").value = s.accent || "emerald";
  });
  $("#set-save").onclick = function () {
    api("/api/admin/school", {
      method: "PATCH",
      body: { name: $("#set-name").value, tagline: $("#set-tagline").value, accent: $("#set-accent").value },
    }).then(function () {
      toast("Réglages enregistrés ✓");
    });
  };
}

/* ============================== init ============================== */
function boot() {
  api("/api/me").then(function (d) {
    STATE.me = d.user;
    STATE.school = d.school;
    if (d.school && d.school.accent) { document.documentElement.setAttribute("data-accent", d.school.accent); }
    $("#side-user").textContent = d.user.name || d.user.email;
    $("#side-school").textContent = d.school ? d.school.name : "CDB Bien-Être";
    if (d.is_admin) { $("#nav-admin").classList.remove("hidden"); }
    navClicks();
    renderDash();
  }).catch(function () {});
}

/* boutons admin câblés une seule fois */
var BTN_NEW_COURSE = $("#btn-new-course");
if (BTN_NEW_COURSE) { BTN_NEW_COURSE.onclick = newCourseModal; }
var BTN_ENROLL = $("#btn-enroll");
if (BTN_ENROLL) { BTN_ENROLL.onclick = enrollModal; }
var BTN_CODES = $("#btn-new-codes");
if (BTN_CODES) { BTN_CODES.onclick = newCodesModal; }
var BTN_PACK = $("#btn-new-pack");
if (BTN_PACK) { BTN_PACK.onclick = newPackModal; }
var REDEEM_BTN = $("#redeem-btn");
if (REDEEM_BTN) { REDEEM_BTN.onclick = doRedeem; }

function doRedeem() {
  var inp = $("#redeem-input");
  var code = (inp.value || "").trim();
  if (!code) { toast("Saisis un code d'accès", true); return; }
  api("/api/redeem", { method: "POST", body: { code: code } }).then(function (r) {
    if (r.ok) {
      inp.value = "";
      toast(r.already ? "Déjà débloqué — bonne lecture ✦" : "Débloqué : " + (r.course_title || "formation") + " ✦");
      renderDash();
    } else { toast(r.error || "Code invalide", true); }
  });
}

boot();