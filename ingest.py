# ARCHIVÉ (16/10/2026) : cet ingest était dédié à la numérologie (fichiers Drive Rosemary).
# Pour le LMS Bien-Être, les contenus seedés vivent dans seed_data.py (+ upload PDF/vidéo par l'admin).
# Conservé pour la mécanique docx→leçons réutilisable (pattern Drive).
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest.py — Rosémary LMS : ingestion RÉELLE des contenus Drive (.docx)
→ reconstruit les 3 formations (modules/leçons riches avec images extraites),
→ attache les supports originaux (.docx) téléchargeables,
→ quiz par formation, préviews gratuits, réinscription de l'élève démo.

Idempotent : reconstruit les formations à partir de leurs slugs seed.
"""
import json
import os
import re
import zipfile
from xml.etree import ElementTree as ET

import db
import seed_data

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DRIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drive")
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "assets")
os.makedirs(ASSETS, exist_ok=True)

MEDIA = []
_img_n = 0


def norm(s: str) -> str:
    s = s.replace("’", "'")           # apostrophe typographique → droite
    s = re.sub(r"\d+$", "", s.strip())
    s = re.sub(r"^\d+(?:[.\-]\d+)*\s*", "", s)
    return re.sub(r"\s+", " ", s).strip()


# ==================================================================
# 1. Parser docx robuste (1 seul ZipFile, images inline extraites)
# ==================================================================
def parse_docx(path):
    out = []
    with zipfile.ZipFile(path) as z:
        rels = {}
        try:
            rels_xml = ET.fromstring(z.read("word/_rels/document.xml.rels"))
            for rel in rels_xml:
                rels[rel.get("Id")] = rel.get("Target") or ""
        except KeyError:
            pass
        root = ET.fromstring(z.read("word/document.xml"))
        body = root.find(W + "body")

        def para(p):
            ps = p.find(W + "pPr/" + W + "pStyle")
            style = (ps.get(W + "val") or "").lower() if ps is not None else ""
            parts = []
            for child in p.iter():
                if child.tag == W + "t":
                    parts.append(child.text or "")
                elif child.tag == W + "br":
                    parts.append("<br>")
                elif child.tag == A + "blip":
                    rid = child.get(R + "embed")
                    target = (rels.get(rid) or "").lstrip("/").lower()
                    for cand in (target, "word/" + target, "word/media/" + os.path.basename(target)):
                        if cand and _ext_ok(cand):
                            src = _save_media(z, cand)
                            if src:
                                parts.append('<img src="' + src + '" alt="illustration">')
                            break
                elif child.tag == W + "tab":
                    parts.append(" — ")
            text = re.sub(r"\s+", " ", "".join(parts)).strip()
            if not text:
                return None
            text = re.sub(r"^(?:<br>\s*)+", "", text)   # <br> parasite avant titre → sinon regex ^ ratent le titre
            if not text:
                return None
            kind = "p"
            if re.match(r"heading[1]?$|titre\s*1$", style):
                kind = "h1"
            elif re.match(r"heading[2]$|titre\s*2$", style):
                kind = "h2"
            elif re.match(r"heading[34]$|titre\s*[34]$", style):
                kind = "h3"
            return {"kind": kind, "raw": text}

        def tbl(t):
            rows = []
            for tr in t.findall(W + "tr"):
                cells = []
                for tc in tr.findall(W + "tc"):
                    cells.append("<td>" + "".join((x.text or "") for x in tc.iter(W + "t")).strip() + "</td>")
                if cells:
                    rows.append("<tr>" + "".join(cells) + "</tr>")
            if rows:
                return {"kind": "p", "raw": "<table>" + "".join(rows) + "</table>"}
            return None

        for el in body:
            if el.tag == W + "p":
                b = para(el)
            elif el.tag == W + "tbl":
                b = tbl(el)
            else:
                b = None
            if b:
                out.append(b)
    return out


def _ext_ok(name):
    return bool(re.search(r"\.(png|jpe?g|gif|webp|bmp)$", name))


def _save_media(z, member):
    global _img_n
    try:
        data = z.read(member)
    except KeyError:
        return None
    ext = member.rsplit(".", 1)[-1].lower()
    _img_n += 1
    name = "lmsimg_%03d.%s" % (_img_n, ext)
    with open(os.path.join(ASSETS, name), "wb") as f:
        f.write(data)
    MEDIA.append(name)
    return "/static/assets/" + name


# ==================================================================
# 2. Helpers de segmentation
# ==================================================================
def segcut(blocks, rules, cut_on_p_allcaps=True):
    """rules: liste (regex_sur_norm, key).
    Cut sur h1/h2/h3 OU sur paragraphes « titres visuels » (tout-majuscules, court)."""
    segs = {"pre": []}
    cur = "pre"
    for b in blocks:
        raw = b["raw"]
        n = norm(raw)
        is_head = b["kind"] in ("h1", "h2", "h3")
        # p « titre visuel » : LIGNE EN MAJUSCULES courte, sans <table>
        is_p_title = False
        if cut_on_p_allcaps and b["kind"] == "p" and "<table" not in raw and 0 < len(n) < 90:
            letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", n)
            uppers = re.sub(r"[^A-ZÀ-Ý]", "", n)
            if letters and uppers.upper() == letters:
                is_p_title = True
        if is_head or is_p_title:
            for rx, key in rules:
                if re.search(rx, n, re.I):
                    cur = key
                    break
        segs.setdefault(cur, [])
        segs[cur].append(b)
    return segs


def join_blocks(blocks):
    """Blocs → HTML leçon."""
    html = ""
    for b in blocks:
        t = b["raw"]
        if t.startswith("<table"):
            html += t + "<br>"
        elif b["kind"] in ("h1", "h2", "h3"):
            html += "<h3>" + t + "</h3>"
        else:
            html += "<p>" + t + "</p>"
    return html or "<p>Contenu à l'étude.</p>"


def split_by_number(blocks, rx):
    """Splitte un segment en buckets par numéro détecté dans le TEXTE BRUT (pas le norm)."""
    buckets = []
    cur = None
    for b in blocks:
        m = re.match(rx, b["raw"], re.I) if b["kind"] != "p" or True else None
        m = re.match(rx, b["raw"], re.I)
        if m:
            cur = {"n": m.group(1), "blocks": []}
            buckets.append(cur)
        elif cur and not buckets:
            buckets.append({"n": "0", "blocks": []})
            cur = buckets[0]
        if cur is not None:
            cur["blocks"].append(b)
    return buckets


# ==================================================================
# 3. Segmentation par document
# ==================================================================
print("lecture des .docx…")
DOC_NP = parse_docx(os.path.join(DRIVE, "SOMMAIRE NOM ET PRENOM PART 1.docx"))
DOC_INC = parse_docx(os.path.join(DRIVE, "SOMMAIRE TABLE D'INCLUSION.docx"))
DOC_CH = parse_docx(os.path.join(DRIVE, "SOMMAIRE CHEMIN DE VIE.docx"))
DOC_AN = parse_docx(os.path.join(DRIVE, "SOMMAIRE ANNEE PERSONNELLE.docx"))
DOC_EX = parse_docx(os.path.join(DRIVE, "SOMMAIRE EXPRESSION LETTRE.docx"))
print("blocs:", {k: len(v) for k, v in (("NP", DOC_NP), ("INC", DOC_INC), ("CH", DOC_CH), ("AN", DOC_AN), ("EX", DOC_EX))})
print("images extraites:", len(MEDIA))

# ---- NOM & PRÉNOM (F1 + F2 + dettes F3) — tout ancré, ordre = priorité ----
S_NP = segcut(DOC_NP, [
    (r"^TOUT EST NOMBRE", "f1m1"),
    (r"^LE SYMBOLISME DES NOMBRES", "f1m2"),
    (r"^SIGNIFICATIONS DE BASE DES MAITRES", "f1m3"),
    (r"^QUELQUES REPERES", "f1m3b"),
    (r"^LE CHIFFRAGE DES LETTRES", "f1m4"),
    (r"^LE NOMBRE ACTIF\b", "f1m5"),
    (r"^LE NOMBRE HEREDI|HÉRÉDIT\w*", "f1m6"),
    (r"^VECU|VÉCU", "f2m1"),
    (r"^L'ELAN SPIRITUEL|^L'ÉLAN SPIRITUEL|^ELAN SPIRITUEL|^ÉLAN SPIRITUEL", "f2m2"),
    (r"^LE NOMBRE DE REALISATION|^LE NOMBRE DE RÉALISATION|^NOMBRE DE RÉALISATION|^NOMBRE DE REALISATION", "f2m3"),
    (r"^LE NOMBRE D'EXPRESSION|^NOMBRE D'EXPRESSION", "f2m4"),
    (r"^ESSENCE DU NOMBRE DU CARACT", "f2m5a"),
    (r"^ESSENCE DE|^ESSENCE DU|^ESSENCE [1-9]", "f2m5a"),
    (r"^(LE )?D[ÉE]FIS PSYCHOLOGIQUES|^LE D[ÉE]FI ", "f2m5b"),
    (r"^LES LETTRES?$|^LE D[ÉE]FI DES LETTRES|^PRESENTATION DANS LE CADRE|^PRÉSENTATION DANS LE CADRE", "f2m6"),
    (r"^L{1,2}ES?E?TTRES C[ÉE]R[ÉE]BRALES|^LETTRES CEREBRALES|^LETTRES C[ÉÉ]R[ÉÉ]BRALES", "f2m7a"),
    (r"^LETTRES INTUITIVES", "f2m7b"),
    (r"^LETTRES PHYSIQUES", "f2m8a"),
    (r"^LETTRES CR[ÉE]ATRICES", "f2m8b"),
    (r"^LETTRES [ÉE]MOTIVES", "f2m8c"),
    (r"^LETTRES IMMOBILES", "f2m9a"),
    (r"^LETTRES MOBILES", "f2m9b"),
    (r"^LES INITIALES", "f2m10"),
    (r"^LES DETTES KARMIQUES", "f3m2"),
    (r"^TABLEAU PLAN DU CARACT", "f3m10"),
    (r"^NOMBRE ACTIF \+ NOMBRE H", "f3m10b"),
])
# resplit : depuis f1m2, chaque titre « LE NOMBRE [k] » ouvre un bucket (1..3 implicites)
S_NP["f3m1"] = []
keep = []
_buckets, cur_b = [], None
for b in S_NP.get("f1m2", []):
    n_txt = norm(b["raw"])
    m = re.match(r"^LE NOMBRE\s*([1-9]?[0-9])?$", n_txt, re.I)
    if m and len(n_txt) < 16:
        num = m.group(1) or str(len(_buckets) + 1)
        cur_b = {"n": num, "blocks": []}
        _buckets.append(cur_b)
        continue
    def _is_pt(b):
        n0 = norm(b["raw"])
        if b["kind"] != "p" or "<table" in n0 or not (0 < len(n0) < 90):
            return False
        letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", n0)
        uppers = re.sub(r"[^A-ZÀ-Ý]", "", n0)
        return bool(letters) and uppers.upper() == letters

    heading_non_nombre = (b["kind"] in ("h1", "h2", "h3") and not n_txt.startswith("LE NOMBRE")) or \
        (_is_pt(b) and not n_txt.startswith("LE NOMBRE"))
    if heading_non_nombre:
        # fin de la zone nombres (ex. SIGNIFICATIONS MAITRES) → on verse les buckets
        for bk in _buckets:
            if int(bk["n"]) >= 10:
                bk["blocks"].insert(0, {"kind": "p", "raw": "LE NOMBRE " + bk["n"]})
                S_NP["f3m1"].append(bk)
            else:
                keep.append({"kind": "h3", "raw": "LE NOMBRE " + bk["n"]})
                keep.extend(bk["blocks"])
        _buckets, cur_b = [], None
        keep.append(b)
        continue
    if cur_b is not None:
        cur_b["blocks"].append(b)
    else:
        keep.append(b)
for bk in _buckets:  # fin de segment → versement final
    if int(bk["n"]) >= 10:
        bk["blocks"].insert(0, {"kind": "p", "raw": "LE NOMBRE " + bk["n"]})
        S_NP["f3m1"].append(bk)
    else:
        keep.append({"kind": "h3", "raw": "LE NOMBRE " + bk["n"]})
        keep.extend(bk["blocks"])
S_NP["f1m2"] = keep
# dans f3m1 (buckets) : isoler les dettes 13/14/16/19 → f3m1b
S_NP["f3m1b"] = []
det_nums = {"13", "14", "16", "19"}
composes = []
for bk in S_NP["f3m1"]:
    (S_NP["f3m1b"] if bk["n"] in det_nums else composes).append(bk)
S_NP["f3m1"] = composes

# ---- INCLUSION (F3) — occurrences dynamiques ----
S_INC = {"pre": [], "cases": [], "grille": [], "nombres": [], "axes": [], "recap": []}
inc_occ = 0
cur = "pre"
for b in DOC_INC:
    if b["kind"] in ("h1", "h2", "h3"):
        n = norm(b["raw"])
        raw = b["raw"]
        mmod = re.search(r"MODULATEURS DANS LA CASES? D['’]INCLUSION\s*(\d+)", raw, re.I)
        if mmod:
            cur = "mod" + mmod.group(1)
            S_INC.setdefault(cur, [])
        elif re.search(r"CONCERNANT L", n, re.I):
            cur = "recap"
        elif re.search(r"LES NOMBRES DANS LES CASES", n, re.I):
            cur = "nombres"
        elif re.search(r"LA GRILLE D", n, re.I):
            cur = "grille"
        elif re.search(r"LES CASES DANS LA GRILLE", n, re.I):
            cur = "cases"
        elif re.search(r"L['’]INCLUSION", n, re.I):
            inc_occ += 1
            cur = {1: "inc1", 2: "grille", 3: "axes"}.get(inc_occ, "axes")
        else:
            cur = cur if cur in ("pre",) else cur  # heading isolé → seg courant
    S_INC.setdefault(cur, [])
    S_INC[cur].append(b)

# ---- CHEMIN DE VIE (F2 m11) — numéros depuis le raw ----
S_CH = {"intro": []}
cur_chem = None
for b in DOC_CH:
    if b["kind"] in ("h1", "h2", "h3"):
        n = norm(b["raw"]).rstrip(".")
        if re.search(r"RÉALISATIONS DU CHEMIN", n, re.I):
            cur_chem = "realisations"
        elif re.search(r"RÉALISATIONS UNIVERSELLES", n, re.I):
            cur_chem = "universelles"
        elif re.search(r"L'ESSENCE DU CHEMIN", n, re.I):
            cur_chem = "essence"
        elif re.search(r"LE JOUR DE NAISSANCE", n, re.I):
            cur_chem = "jour"
        elif re.search(r"LE MOIS DE NAISSANCE", n, re.I):
            cur_chem = "mois"
        elif re.search(r"CYCLES DE VIE", n, re.I):
            cur_chem = "cycles"
        elif re.search(r"APOGÉES|APOGEES", n, re.I):
            cur_chem = "apogees"
        elif re.search(r"^LES DÉFIS$|LES DE?FIS\b", n, re.I):
            cur_chem = "defis"
        elif re.search(r"NOMBRE DU BUT", n, re.I):
            cur_chem = "but"
        elif re.search(r"VOCATION", n, re.I):
            cur_chem = "vocation"
        elif re.search(r"DEUX PÉRIODES|PÉRIODES DE L", n, re.I):
            cur_chem = "periodes"
        else:
            cur_chem = None  # heading CHEMIN DE VIE / TABLEAU DATE → intro
    S_CH.setdefault(cur_chem or "intro", [])
    S_CH[cur_chem or "intro"].append(b)

# ---- ANNÉE PERSONNELLE (F2 m12) — « 1-1 ANNÉE PERSONNELLE » (et variantes serrées) ----
S_AN = {"intro": []}
cur_grp = 0
for b in DOC_AN:
    m = re.search(r"(\d+)\s*[-–]?\s*\d*\s*ANN[ÉE]E\s+PERSONNELLE", b["raw"], re.I)
    if m:
        n = int(m.group(1))
        cur_grp = 1 if n <= 3 else (2 if n <= 6 else 3)
        S_AN[cur_grp] = S_AN.get(cur_grp) or []
        S_AN[cur_grp].append(b)
        continue
    if re.search(r"ANN[ÉE]E PERSONNELLE", b["raw"], re.I) and cur_grp == 0 and b["kind"] in ("h1", "h2", "h3"):
        continue
    S_AN["intro"].append(b)
S_AN = {"intro": S_AN["intro"], 1: S_AN.get(1, []), 2: S_AN.get(2, []), 3: S_AN.get(3, [])}
print("années: intro=%s g1=%s g2=%s g3=%s" % (len(S_AN["intro"]), len(S_AN[1]), len(S_AN[2]), len(S_AN[3])))
dbg = {k: len(v) for k, v in S_NP.items() if v}
print("segments NP:", dbg)
dbg2 = {k: len(v) for k, v in S_INC.items() if v}
print("segments INC:", dbg2)
dbg3 = {k: len(v) for k, v in S_CH.items() if v}
print("segments CH:", dbg3)

# ==================================================================
# 4. Plan des leçons par formation
# ==================================================================
def grp3(buckets, per=3):
    """[(n, blocks)] → leçons groupées par `per` nombres."""
    out, buf = [], []
    for bk in buckets:
        buf.append(bk)
        if len(buf) >= per:
            out.append(buf); buf = []
    if buf:
        out.append(buf)
    return out


def lessons_numbers(buckets, label_fmt, per=3, start_count=1):
    ls = []
    for grp in grp3(buckets, per):
        ns = [int(g["n"]) for g in grp if g["n"].isdigit()]
        html = "".join(join_blocks(g["blocks"]) for g in grp)
        titre = label_fmt % (min(ns), max(ns)) if len(ns) > 1 else (label_fmt % (ns[0], ns[0]) if ns else label_fmt % ("…", "…"))
        titre = re.sub(r"\s*—\s*$", "", titre)
        ls.append({"title": titre, "html": html})
    return ls


PLAN = {}

# ---------- FORMATION 1 ----------
f1_modules = []
f1_modules.append({"title": "Module 1 — Les Fondements de la Numérologie",
                   "desc": "Origines, Pythagore, les nombres comme vibrations vivantes",
                   "lessons": [{"title": "Tout est nombre — disait Pythagore", "html": join_blocks(S_NP["f1m1"])}]})
sym_ls = lessons_numbers(split_by_number(S_NP["f1m2"], r"^LE NOMBRE\s*([1-9])\b"), "Le nombre %s à %s", 3)
if sym_ls:
    f1_modules.append({"title": "Module 2 — Le Symbolisme des Nombres 1 à 9",
                       "desc": "Significations positives/négatives, mots clefs, éléments, astrologie",
                       "lessons": sym_ls})
if S_NP.get("f1m3"):
    l1 = {"title": "Les Maîtres Nombres 11, 22, 33", "html": join_blocks(S_NP["f1m3"])}
    f1m3_ls = [l1]
    if S_NP.get("f1m3b"):
        f1m3_ls.append({"title": "Quelques repères sur les nombres", "html": join_blocks(S_NP["f1m3b"])})
    f1_modules.append({"title": "Module 3 — Les Maîtres Nombres 11, 22, 33",
                       "desc": "Énergie supérieure et conditions d'expression",
                       "lessons": f1m3_ls})
if S_NP.get("f1m4"):
    f1_modules.append({"title": "Module 4 — Le Chiffrage des Lettres",
                       "desc": "Table de correspondance, les 3 décades (spirituel, émotionnel, physique)",
                       "lessons": [{"title": "La table de chiffrage A=1 … Z=26/8", "html": join_blocks(S_NP["f1m4"])}]})
if S_NP.get("f1m5"):
    actif_ls = [{"title": "Le Nombre Actif — calcul et significations 1 à 22", "html": join_blocks(S_NP["f1m5"])}]
    f1_modules.append({"title": "Module 5 — Le Nombre Actif (Prénom)",
                       "desc": "50 % de la personnalité dynamique, significations de 1 à 22",
                       "lessons": actif_ls})
if S_NP.get("f1m6"):
    f1_modules.append({"title": "Module 6 — Le Nombre Héréditaire (Nom)",
                       "desc": "Composante génétique et spirituelle, héritage familial",
                       "lessons": [{"title": "Le Nombre Héréditaire — l'héritage du nom", "html": join_blocks(S_NP["f1m6"])}]})
PLAN["formation-1-identite-numerologique"] = {
    "title": "Formation 1 — Découvrez Votre Identité Numérologique",
    "subtitle": "Les fondations : symbolisme des nombres, chiffrage, Nombre Actif & Héréditaire",
    "level": "débutant", "price": 147, "old_price": 197, "duration": "8 à 10 heures",
    "color": "#2DE28E", "modules": f1_modules,
    "quiz": seed_data.QUIZ_M1_F1 + seed_data.QUIZ_M2_F1,
    "support": "SOMMAIRE NOM ET PRENOM PART 1.docx",
}

# ---------- FORMATION 2 ----------
f2_modules = []
if S_NP.get("f2m1"):
    f2_modules.append({"title": "Module 1 — Les Postes Clefs du Thème",
                       "desc": "Vécu/Inné, prénom usuel vs tous les prénoms, les 5 postes fondamentaux",
                       "lessons": [{"title": "Vécu / Inné — les 5 postes clefs", "html": join_blocks(S_NP["f2m1"])}]})
if S_NP.get("f2m2"):
    f2_modules.append({"title": "Module 2 — L'Élan Spirituel (voyelles)",
                       "desc": "Aspirations profondes, motivations secrètes",
                       "lessons": [{"title": "L'Élan Spirituel — tes aspirations profondes", "html": join_blocks(S_NP["f2m2"])}]})
if S_NP.get("f2m3"):
    f2_modules.append({"title": "Module 3 — Le Nombre de Réalisation (consonnes)",
                       "desc": "Outils de vie, buts concrets à atteindre",
                       "lessons": [{"title": "Le Nombre de Réalisation — tes outils de vie", "html": join_blocks(S_NP["f2m3"])}]})
if S_NP.get("f2m4"):
    f2_modules.append({"title": "Module 4 — Le Nombre d'Expression",
                       "desc": "Mode d'action prioritaire, identité publique et relationnelle",
                       "lessons": [{"title": "Le Nombre d'Expression — ton mode d'action", "html": join_blocks(S_NP["f2m4"])}]})
ess_ls = []
if S_NP.get("f2m5a"):
    ess_ls.append({"title": "L'Essence du Caractère", "html": join_blocks(S_NP["f2m5a"])})
if S_NP.get("f2m5b"):
    ess_ls.append({"title": "Les Défis Psychologiques", "html": join_blocks(S_NP["f2m5b"])})
if ess_ls:
    f2_modules.append({"title": "Module 5 — L'Essence du Caractère et les Défis",
                       "desc": "Transformation des obstacles en leviers de croissance", "lessons": ess_ls})
if S_NP.get("f2m6"):
    intro_lettres = join_blocks(S_NP["f2m6"]) + (join_blocks(S_NP["f2m6b"]) if S_NP.get("f2m6b") else "")
    f2_modules.append({"title": "Module 6 — Les Lettres et le Plan d'Expression",
                       "desc": "Les 26 lettres, leurs valeurs numériques et vibratoires",
                       "lessons": [{"title": "Les 26 lettres et le plan d'expression", "html": intro_lettres}]})
let_ls = []
for key, titre in (("f2m7a", "Les lettres cérébrales"), ("f2m7b", "Les lettres intuitives")):
    if S_NP.get(key):
        let_ls.append({"title": titre, "html": join_blocks(S_NP[key])})
if let_ls:
    f2_modules.append({"title": "Module 7 — Les Lettres Cérébrales et Intuitives",
                       "desc": "Facultés mentales, lucidité, pressentiments, spiritualité", "lessons": let_ls})
let_ls = []
for key, titre in (("f2m8a", "Les lettres physiques"), ("f2m8b", "Les lettres créatrices"), ("f2m8c", "Les lettres émotives")):
    if S_NP.get(key):
        let_ls.append({"title": titre, "html": join_blocks(S_NP[key])})
if let_ls:
    f2_modules.append({"title": "Module 8 — Les Lettres Physiques, Émotives, Créatrices",
                       "desc": "Corps, émotions, dynamisme et passage à l'action", "lessons": let_ls})
let_ls = []
for key, titre in (("f2m9a", "Les lettres immobiles — l'attachement"), ("f2m9b", "Les lettres mobiles — le détachement")):
    if S_NP.get(key):
        let_ls.append({"title": titre, "html": join_blocks(S_NP[key])})
if let_ls:
    f2_modules.append({"title": "Module 9 — Les Lettres Mobiles et Immobiles",
                       "desc": "Adaptabilité, stabilité, fonctionnement dualiste", "lessons": let_ls})
if S_NP.get("f2m10"):
    f2_modules.append({"title": "Module 10 — Les Initiales et le Nombre d'Équilibre",
                       "desc": "Stabilité face aux épreuves, conseils numériques de vie",
                       "lessons": [{"title": "Les initiales et le Nombre d'Équilibre", "html": join_blocks(S_NP["f2m10"])}]})
ch_ls = []
pre_intro = join_blocks(S_CH["intro"]) if S_CH.get("intro") else ""
if pre_intro:
    ch_ls.append({"title": "Le chemin de vie — ton but de vie par la date de naissance", "html": pre_intro})
big = split_by_number(S_CH["intro"] if S_CH.get("intro") else [], r"^(\d+(?:\.\d+)*)\s*CHEMIN DE VIE")
if big:
    for grp in grp3(big, 3):
        html = "".join(join_blocks(g["blocks"]) for g in grp)
        ns = []
        for g in grp:
            try:
                ns.append(int(g["n"].split(".")[0]))
            except Exception:
                pass
        ch_ls.append({"title": "Chemin de vie %s" % ("—".join(str(x) for x in (min(ns), max(ns))) if len(ns) > 1 else str(ns[0] if ns else "?")), "html": html})
for key, titre, desc_l in (
        ("realisations", "Les réalisations du chemin de vie", ""),
        ("universelles", "Les réalisations universelles", ""),
        ("essence", "L'essence du chemin de vie", ""),
        ("jour", "Le jour de naissance", ""),
        ("mois", "Le mois de naissance", ""),
        ("cycles", "Les cycles de vie", ""),
        ("apogees", "Les apogées de réalisation", ""),
        ("defis", "Les défis du chemin de vie", ""),
        ("but", "Le nombre du but", ""),
        ("vocation", "La vocation professionnelle", ""),
        ("periodes", "Les deux périodes de l'existence", "")):
    if S_CH.get(key):
        ch_ls.append({"title": titre, "html": join_blocks(S_CH[key])})
if ch_ls:
    f2_modules.append({"title": "Module 11 — Le Chemin de Vie",
                       "desc": "Comprendre ce que nous devons réaliser — période, orientation, date de naissance",
                       "lessons": ch_ls})
an_ls = []
if S_AN.get("intro"):
    an_ls.append({"title": "L'année personnelle — ton climat du moment", "html": join_blocks(S_AN["intro"])})
for g, titre in (("1", "Les années personnelles 1 à 3"), ("2", "Les années personnelles 4 à 6"), ("3", "Les années personnelles 7 à 9")):
    if S_AN.get(g) and S_AN[g]:
        an_ls.append({"title": titre, "html": join_blocks(S_AN[g])})
if an_ls:
    f2_modules.append({"title": "Module 12 — L'Année Personnelle",
                       "desc": "Mise en harmonie du thème de naissance avec la période en cours",
                       "lessons": an_ls})
PLAN["formation-2-caractere-et-destinee"] = {
    "title": "Formation 2 — Décryptez Votre Caractère et Votre Destinée",
    "subtitle": "Postes clefs, élan spirituel, réalisation, expression, lettres, chemin de vie et année personnelle",
    "level": "intermédiaire", "price": 397, "old_price": 497, "duration": "15 à 20 heures",
    "color": "#5CE2B8", "modules": f2_modules,
    "quiz": seed_data.QUIZ_M1_F2 + seed_data.QUIZ_M2_F2,
    "supports": {"f2m10": "SOMMAIRE NOM ET PRENOM PART 1.docx", "last": "SOMMAIRE CHEMIN DE VIE.docx"},
    "support_last2": "SOMMAIRE ANNEE PERSONNELLE.docx",
}

# ---------- FORMATION 3 ----------
f3_modules = []
comp_ls = []
for grp in grp3(S_NP["f3m1"], 3):
    html = "".join(join_blocks(g["blocks"]) for g in grp)
    ns = [int(g["n"]) for g in grp if g["n"].isdigit()]
    comp_ls.append({"title": "Nombres %s à %s" % (min(ns), max(ns)) if len(ns) > 1 else "Le nombre %s" % ns[0], "html": html})
if comp_ls:
    f3_modules.append({"title": "Module 1 — Les Nombres Composés 10 à 22",
                       "desc": "Double vibration, sens karmique et applicatif avancé", "lessons": comp_ls})
det_ls = []
NUMS_D = {13: "travail détourné", 14: "liberté mal employée", 16: "amours / égo détruits", 19: "pouvoir abusif"}
for bk in S_NP["f3m1b"]:
    n = int(bk["n"])
    det_ls.append({"title": "La dette karmique %s — %s" % (n, NUMS_D.get(n, "")), "html": join_blocks(bk["blocks"])})
if S_NP.get("f3m2"):
    det_ls.append({"title": "Les karmiques secondaires et le tableau des dettes", "html": join_blocks(S_NP["f3m2"])})
if det_ls:
    f3_modules.append({"title": "Module 2 — Les Dettes Karmiques 13, 14, 16, 19",
                       "desc": "Significations, présence dans le thème, conseils d'épuration", "lessons": det_ls})
inc_ls = []
if S_INC.get("inc1"):
    inc_ls.append({"title": "Construire la grille d'Inclusion 3×3 — Vécu et Inné", "html": join_blocks(S_INC["inc1"])}); 
if S_INC.get("grille"):
    inc_ls.append({"title": "La grille d'Inclusion pas à pas", "html": join_blocks(S_INC["grille"])})
if S_INC.get("cases"):
    inc_ls.append({"title": "Les 9 cases et leurs significations", "html": join_blocks(S_INC["cases"])})
if inc_ls:
    f3_modules.append({"title": "Module 3 — Introduction à la Table d'Inclusion",
                       "desc": "Construction de la grille 3×3, Vécu et Inné, nombres manquants/dominants", "lessons": inc_ls})
if S_INC.get("nombres"):
    f3_modules.append({"title": "Module 4 — Les Nombres dans les Cases",
                       "desc": "Équilibre, vide, faible, excès : interprétation précise",
                       "lessons": [{"title": "Nombres dans les cases équilibre, vide, faible, excès", "html": join_blocks(S_INC["nombres"])}]})
if S_INC.get("axes"):
    f3_modules.append({"title": "Module 5 — Les Axes de la Grille",
                       "desc": "Horizontal (Ego, Matériel, Pouvoir), Vertical (Force, Instinct, Sociabilité), Diagonal (Réussite, Leadership)",
                       "lessons": [{"title": "Les axes horizontaux, verticaux et diagonaux", "html": join_blocks(S_INC["axes"])}]})
mod_ls = []
for i in range(1, 10):
    k = "mod%d" % i
    if S_INC.get(k):
        mod_ls.append({"title": "Les modulateurs — case %d" % i, "html": join_blocks(S_INC[k])})
if mod_ls:
    f3_modules.append({"title": "Module 6 — Les Modulateurs dans les Cases 1 à 9",
                       "desc": "Analyse fine des associations case/modulateur pour chaque numéro", "lessons": mod_ls})
recap_parts = ""
if S_INC.get("recap"):
    recap_parts += join_blocks(S_INC["recap"])
if S_NP.get("f3m10"):
    recap_parts += join_blocks(S_NP["f3m10"])
if recap_parts:
    f3_modules.append({"title": "Module 7 — Tableau Récapitulatif et Consultation",
                       "desc": "Construction d'un thème complet de A à Z, cas pratiques réels",
                       "lessons": [{"title": "Construire un thème complet — cas pratique", "html": recap_parts}]})
PLAN["formation-3-karmique-et-inclusion"] = {
    "title": "Formation 3 — Maîtrisez la Numérologie Karmique et l'Inclusion",
    "subtitle": "Nombres composés, dettes karmiques, Table d'Inclusion 3×3 — le niveau consultant",
    "level": "expert", "price": 997, "old_price": 1297, "duration": "25 à 35 heures",
    "color": "#8B5CF6", "modules": f3_modules,
    "quiz": seed_data.QUIZ_M1_F3 + seed_data.QUIZ_M2_F3,
    "support": "SOMMAIRE TABLE D'INCLUSION.docx",
}

# ==================================================================
# 5. Reconstruction DB (cascades maîtrisées)
# ==================================================================
conn = db.get_conn()
school = db.q1(conn, "SELECT id FROM schools WHERE slug='rosemary'")
SCHOOL_ID = school["id"]
demo = db.q1(conn, "SELECT id FROM users WHERE email='demo@cdb-hub.app'")
DEMO_ID = demo["id"] if demo else None

print()
for slug, P in PLAN.items():
    old = db.q1(conn, "SELECT id FROM courses WHERE school_id=? AND slug=?", (SCHOOL_ID, slug))
    if old:
        oid = old["id"]
        db.ex(conn, "DELETE FROM progress WHERE course_id=?", (oid,))
        db.ex(conn, "DELETE FROM enrollments WHERE course_id=?", (oid,))
        db.ex(conn, "DELETE FROM access_codes WHERE course_id=?", (oid,))
        db.ex(conn, "DELETE FROM certificates WHERE course_id=?", (oid,))
        db.ex(conn, "UPDATE announcements SET course_id=NULL WHERE course_id=?", (oid,))
        db.ex(conn, "DELETE FROM courses WHERE id=?", (oid,))
        print("  reconstruit:", slug)

for pos, (slug, P) in enumerate(PLAN.items()):
    cid = db.new_id()
    desc = seed_data.ALL_COURSES[pos]["desc"]
    db.ex(conn, """INSERT INTO courses (id, school_id, slug, title, subtitle, description_html, level,
                   price, old_price, duration_hours, color_card, cover_url, status, position, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (cid, SCHOOL_ID, slug, P["title"], P["subtitle"], desc, P["level"], P["price"],
           P["old_price"], P["duration"], P["color"], "", "published", pos, db.now()))
    mpos = 0
    for mi, m in enumerate(P["modules"]):
        mid = db.new_id()
        db.ex(conn, "INSERT INTO modules (id, course_id, title, description, position) VALUES (?,?,?,?,?)",
              (mid, cid, m["title"], m["desc"], mpos))
        mpos += 1
        for lpos, l in enumerate(m["lessons"]):
            lid = db.new_id()
            db.ex(conn, """INSERT INTO lessons (id, module_id, course_id, title, content_html, video_url,
                           position, free_preview, drip_days, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (lid, mid, cid, l["title"], l["html"], "", lpos,
                   1 if (mi == 0 and lpos == 0) else 0, 0, db.now()))
    # quiz de formation : sur la DERNIÈRE leçon du DERNIER module
    last_mod = P["modules"][-1]
    last_lesson = db.q1(conn, "SELECT id FROM lessons WHERE module_id=? ORDER BY position DESC LIMIT 1",
                        (db.q1(conn, "SELECT id FROM modules WHERE course_id=? ORDER BY position DESC LIMIT 1", (cid,))["id"],))["id"]
    qid = db.new_id()
    db.ex(conn, "INSERT INTO quizzes (id, lesson_id, title, pass_score) VALUES (?,?,?,?)",
          (qid, last_lesson, "Quiz final — %s" % P["title"][:40], 70))
    for i, q in enumerate(P["quiz"]):
        db.ex(conn, "INSERT INTO quiz_questions (id, quiz_id, question, options, correct, explanation, position) VALUES (?,?,?,?,?,?,?)",
              (db.new_id(), qid, q["question"], json.dumps(q["options"], ensure_ascii=False), q["correct"], q["explanation"], i))
    # support docx complet en téléchargement (dernière leçon)
    supp = P.get("support")
    if supp:
        with open(os.path.join(DRIVE, supp), "rb") as f:
            data = f.read()
        ll = db.q1(conn, "SELECT id FROM lessons WHERE module_id=? ORDER BY position DESC LIMIT 1",
                   (db.q1(conn, "SELECT id FROM modules WHERE course_id=? ORDER BY position DESC LIMIT 1", (cid,))["id"],))["id"]
        db.ex(conn, "UPDATE lessons SET pdf_data=?, pdf_name=? WHERE id=?", (data, supp, ll))

# réinscriptions + codes (formation 1)
f1 = db.q1(conn, "SELECT id FROM courses WHERE school_id=? AND slug LIKE 'formation-1%'", (SCHOOL_ID,))
if f1 and DEMO_ID:
    db.ex(conn, "INSERT OR IGNORE INTO enrollments (id, user_id, course_id, school_id, source, code, status, enrolled_at) VALUES (?,?,?,?,?,?,?,?)",
          (db.new_id(), DEMO_ID, f1["id"], SCHOOL_ID, "code", "RSM-DEMO-2026", "active", db.now()))
if f1:
    for code in ("RSM-DEMO-2026", "RSM-BIENVENUE"):
        if not db.q1(conn, "SELECT id FROM access_codes WHERE code=?", (code,)):
            db.ex(conn, "INSERT INTO access_codes (id, school_id, course_id, code, status, note, created_at) VALUES (?,?,?,?,?,?,?)",
                  (db.new_id(), SCHOOL_ID, f1["id"], code, "active", "code démo", db.now()))
    db.ex(conn, "UPDATE access_codes SET course_id=?, status='active', used_by=NULL, used_at=NULL WHERE code IN ('RSM-DEMO-2026','RSM-BIENVENUE')", (f1["id"],))

conn.close()
print()
print("✅ INGESTION TERMINÉE")
for slug, P in PLAN.items():
    n_l = sum(len(m["lessons"]) for m in P["modules"])
    print("  %s : %d modules / %d leçons" % (slug[:45], len(P["modules"]), n_l))
print("  images:", len(MEDIA), "→ static/assets/")