/* landing.js — LMS Bien-Être (landing publique) v2.0 */
(function () {
  "use strict";

  var RAW = { school: { name: "CDB Bien-Être", accent: "sage" }, courses: [] };
  try { RAW = JSON.parse(document.getElementById("data").textContent); } catch (e) {}

  // Applique l'accent de l'école
  if (RAW.school && RAW.school.accent) {
    document.documentElement.setAttribute("data-accent", RAW.school.accent);
  }

  var $ = function (s, c) { return (c || document).querySelector(s); };
  var esc = function (s) {
    return String(s || "").replace(/[&<>"']/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m];
    });
  };

  // ---------- toast ----------
  function toast(msg, isErr) {
    var root = $("#toast-root");
    if (!root) { return; }
    var t = document.createElement("div");
    t.className = "toast" + (isErr ? " err" : "");
    t.textContent = msg;
    root.appendChild(t);
    setTimeout(function () { t.remove(); }, 4200);
  }

  // ---------- catalogue ----------
  function money(v) {
    if (!v || v <= 0) { return "Offert"; }
    var s = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(v);
    return s + " €";
  }

  var CARD_COLORS = ["#2DE28E", "#5CE2B8", "#8B5CF6", "#2D9CE2", "#D4A843", "#F97316"];

  function renderCourses() {
    var grid = $("#courses-grid");
    if (!grid) { return; }
    var courses = RAW.courses || [];
    if (!courses.length) {
      grid.innerHTML = '<p class="dimmer">Le catalogue arrive très bientôt — contactez-nous pour les inscriptions.</p>';
      return;
    }
    var parts = courses.map(function (c, i) {
      var num = (i + 1);
      var color = c.color_card || CARD_COLORS[i % CARD_COLORS.length];
      var meta = [];
      if (c.duration_hours) { meta.push(esc(c.duration_hours)); }
      meta.push((c.level || "tous niveaux"));
      return '<article class="card card-hover course-card" data-slug="' + esc(c.slug) + '">' +
        '<div class="course-thumb" style="--cc:' + esc(color) + '; background:linear-gradient(135deg,' + esc(color) + ', transparent 140%)"><span class="num">' + num + '</span>' +
        '<span class="badge badge-gold">' + esc(c.level || "") + "</span></div>" +
        '<div class="course-body"><h3>' + esc(c.title) + "</h3><p>" + esc(c.subtitle || "") + "</p>" +
        '<div class="course-meta"><span class="prix">' + money(c.price) +
        (c.old_price ? ' <span class="old">' + money(c.old_price) + "</span>" : "") +
        '</span><span class="duree">' + meta.join(" · ") + "</span></div></div></article>";
    });
    grid.innerHTML = parts.join("");
    $(".course-card", grid) && grid.addEventListener("click", function (ev) {
      var card = ev.target.closest(".course-card");
      if (card) { window.location.href = "/formation/" + card.dataset.slug; }
    });
  }

  // ---------- FAQ ----------
  document.querySelectorAll(".faq-q").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var item = btn.closest(".faq-item");
      item.classList.toggle("open");
    });
  });

  // ---------- lead modal ----------
  function openLead() {
    var m = $("#lead-modal");
    if (m) { m.classList.add("open"); }
  }
  function closeLead() {
    var m = $("#lead-modal");
    if (m) { m.classList.remove("open"); }
  }
  var openBtns = [$("#lead-open")].concat(Array.prototype.slice.call(document.querySelectorAll(".lead-open-2")));
  openBtns.forEach(function (b) { b && b.addEventListener("click", openLead); });
  var closer = $("[data-close-lead]");
  closer && closer.addEventListener("click", closeLead);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeLead(); } });

  var sub = $("#lead-submit");
  sub && sub.addEventListener("click", function () {
    var name = ($("#lead-name") || {}).value || "";
    var email = ($("#lead-email") || {}).value || "";
    var goal = ($("#lead-goal") || {}).value || "";
    if (!email || email.indexOf("@") < 1) { toast("Email invalide", true); return; }
    sub.disabled = true;
    // Content-Type text/plain : simple request sans preflight (piège n°16 du playbook)
    fetch("/api/public/lead", {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: JSON.stringify({ name: name, email: email, goal: goal, school: RAW.school.slug || "bienetre" }),
    }).then(function (r) { return r.json(); }).then(function (d) {
      sub.disabled = false;
      if (d && d.ok) { toast("Reçu ! L'école te recontacte avec un code de bienvenue ✦"); closeLead(); }
      else { toast((d && d.error) || "Erreur d'envoi", true); }
    }).catch(function () { sub.disabled = false; toast("Erreur réseau", true); });
  });

  // ---------- brief transporté depuis la landing (pattern CDB) ----------
  try {
    var sp = new URLSearchParams(location.search);
    var brief = sp.get("brief") || sessionStorage.getItem("bienetre_brief") || "";
    if (brief) {
      sessionStorage.setItem("bienetre_brief", brief);
      var ban = $("#brief-banner");
      if (ban) { $("#brief-text").textContent = brief; ban.classList.remove("hidden"); }
      var goalField = $("#lead-goal");
      if (goalField && !goalField.value) { goalField.value = brief; }
    }
  } catch (e) { /* sessionStorage indisponible */ }

  // ---------- init ----------
  renderCourses();
  // duplique l'ancre du marquee pour boucler proprement (fait statiquement en HTML)
})();