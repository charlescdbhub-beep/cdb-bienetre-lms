/* login.js — LMS Bien-Être v2.0 */
(function () {
  "use strict";
  var MODE = (document.body.dataset.mode === "signup") ? "signup" : "login";

  var $ = function (s) { return document.querySelector(s); };

  var copy = {
    login: { titre: "Bon retour ✦", sous: "Content de te revoir — reprends ta progression là où tu l'avais laissée.", cta: "Se connecter" },
    signup: { titre: "Crée ton compte élève", sous: "30 secondes, gratuit. Ton code d'accès premium débloquera ta formation.", cta: "Créer mon compte" },
  };
  var c = copy[MODE] || copy.login;
  var titreEl = $("#titre");
  if (titreEl) { titreEl.textContent = c.titre; }
  var sousEl = $("#sous-titre");
  if (sousEl) { sousEl.textContent = c.sous; }
  var submit = $("#submit");
  if (submit) { submit.textContent = c.cta; }
  var nameBlock = $("#name-block");
  if (MODE === "login" && nameBlock) { nameBlock.style.display = "none"; }

  function toast(msg, isErr) {
    var root = $("#toast-root") || document.body;
    var t = document.createElement("div");
    t.className = "toast" + (isErr ? " err" : "");
    t.textContent = msg;
    t.style.cssText = "position:fixed;bottom:24px;right:24px;z-index:999;background:#121212;border:1px solid #1E1E1E;border-left:3px solid " + (isErr ? "#F87171" : "#2DE28E") + ";border-radius:12px;padding:13px 20px;font-size:14px;";
    root.appendChild(t);
    setTimeout(function () { t.remove(); }, 4200);
  }

  var form = $("#form");
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var email = ($("#email") || {}).value || "";
    var pw = ($("#password") || {}).value || "";
    var name = ($("#name") || {}).value || "";
    if (!email || email.indexOf("@") < 1 || pw.length < 6) {
      toast("Email valide + mot de passe ≥ 6 caractères requis", true);
      return;
    }
    submit.disabled = true;
    fetch(MODE === "signup" ? "/api/auth/signup" : "/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: pw, name: name }),
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) {
        window.location.href = "/app";
      } else {
        submit.disabled = false;
        toast((d && d.error) || "Connexion impossible", true);
      }
    }).catch(function () { submit.disabled = false; toast("Erreur réseau", true); });
  });
})();