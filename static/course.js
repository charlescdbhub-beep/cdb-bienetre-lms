/* course.js — page publique d'une formation v1.0 */
(function () {
  "use strict";
  var RAW = null;
  try { RAW = JSON.parse(document.getElementById("data").textContent); } catch (e) {}
  if (!RAW) { return; }

  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m];
    });
  };
  document.documentElement.setAttribute("data-accent", (RAW.school || {}).accent || "emerald");

  var c = RAW.course || {};
  var mods = RAW.modules || [];
  document.title = c.title + " — LMS Bien-Être";
  $("#crumb").textContent = "✦ Formation — " + (c.level || "");
  $("#co-title").textContent = c.title || "Formation";
  $("#co-sub").textContent = c.subtitle || "";

  var nLessons = mods.reduce(function (n, m) { return n + (m.lessons || []).length; }, 0);
  var tags = [];
  if (c.level) { tags.push(c.level); }
  if (mods.length) { tags.push(mods.length + " modules"); }
  if (nLessons) { tags.push(nLessons + " leçons"); }
  if (c.duration_hours) { tags.push(c.duration_hours); }
  $("#co-tags").innerHTML = tags.map(function (t) {
    return "<span class='pill_tag badge badge-gray'>" + esc(t) + "</span>";
  }).join("");

  var desc = c.description_html || "<p>La description détaillée arrive bientôt.</p>";
  $("#co-desc").innerHTML = desc; /* HTML fourni par l'admin de l'école */

  if (c.price > 0) {
    $("#co-price").textContent = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(c.price) + " €";
    if (c.old_price) { var o = $("#co-old"); o.hidden = false; o.textContent = c.old_price.toFixed(0) + " €"; }
  } else {
    $("#co-price").textContent = "Gratuit";
  }
  var pts = [
    "Accès immédiat après ton code",
    "Leçons + quiz corrigés",
    "Support PDF téléchargeable",
    "Certificat à 100 % de complétion",
  ];
  $("#co-points").innerHTML = pts.map(function (p) { return "<li>" + esc(p) + "</li>"; }).join("");

  function money2() {
    if (!c.price || c.price <= 0) { return "Gratuit"; }
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(c.price) + " €";
  }
  $("#co-price").textContent = money2();

  var html = "";
  if (!mods.length) { html = "<p class='dimmer'>Le programme sera publié très bientôt.</p>"; }
  mods.forEach(function (m, i) {
    html += '<div class="card mod-card' + (i === 0 ? " open" : "") + '">' +
      '<button class="mod-head2"><strong>' + esc(m.title) + "</strong><span class='dimmer' style='font-size:12.5px'>" +
      (m.lessons || []).length + " leçon(s)</span><span class='chev'>⌄</span></button>" +
      '<div class="mod-lessons">' +
      (m.description ? "<p class='dimmer' style='font-size:13px; margin-bottom:8px'>" + esc(m.description) + "</p>" : "");
    (m.lessons || []).forEach(function (l) {
      html += '<div class="lsn"><span>○</span><span style="flex:1">' + esc(l.title) + "</span>" +
        (l.free ? "<span class='tag'>extrait gratuit</span>" : "") +
        (l.has_video ? "<span class='tag'>🎬</span>" : "") +
        "</div>";
    });
    html += "</div></div>";
  });
  $("#co-modules").innerHTML = html;
  $$(".mod-head2").forEach(function (b) {
    b.addEventListener("click", function () { b.closest(".mod-card").classList.toggle("open"); });
  });
})();