# LMS Bien-Être — Ressources d'accompagnement (v2)

![statut](https://img.shields.io/badge/statut-local-green) ![stack](https://img.shields.io/badge/stack-Python%20stdlib%20%2B%20SQLite-blue) ![port](https://img.shields.io/badge/port-51840-yellow)

**LMS multi-écoles pour les ressources du programme d'accompagnement des praticiens bien-être.**
Fork du Rosemary LMS v1.0 (numérologie) — nouvelles fonctions inspirées Teachizy (reverse-engineering 16/10/2026).

## 🎯 Usage

Chaque praticien accompagné reçoit un compte élève + un code unique qui débloque son parcours :

| Parcours | Prix affiché | Contenu |
|---|---|---|
| **F1 — Kit de démarrage du praticien** | Offert | 2 modules · offre claire, tarifs, témoignages · actions 15 min |
| **F2 — Remplir son agenda en continu** | 397 € | 2 modules · page de réservation, relances utiles |
| **F3 — Le système complet du praticien** | 997 € | 2 modules · tableau de bord 3 chiffres, pipeline, automatisation, marque |
| **📦 Pack « Accompagnement complet »** | 997 € (barré 1 290 €) | F1+F2+F3 débloqués par UN seul code |

## ✨ Fonctions v2 (inspirées Teachizy)

- **Packs** : 1 code débloque N formations (gating admin)
- **💬 Espace coach par leçon** : fil privé élève↔coach (le coach répond depuis l'admin, via l'ID élève)
- **⏱ Temps de visionnage actif** : tick 15 s uniquement quand l'onglet est visible (pause hors onglet automatique) + durée minimale configurable par leçon (blocage « marquer terminée » avec message du temps restant)
- **📜 Attestation d'assiduité** : ≥80 % de complétion, série `BLW-ASS-*` (Qualiopi)
- **🏅 Certificat de réussite** : 100 % + quiz réussis, série `BLW-*`
- **⭐ Satisfaction à chaud** : note 1-5 + commentaire proposée à 100 % ; consultable coach (moyenne)
- **🏷 Tags élèves** : segments libres filtrables (ex : vip, atelier-janvier)
- **Drip deux modes** : `drip_days` (J+n leçons finies) ou `drip_date` (libération à une date ISO précise)
- Codes promo/premium en lot, leads vitrine, annonces, stats admin (héritées v1)

## 🏗️ Stack

```
Python 3 stdlib (http.server ThreadingHTTPServer) · port 51840
SQLite WAL · 21 tables (16 Rosemary + lesson_time / lesson_comments / feedback / packs / pack_courses)
bcrypt + sessions SQLite (cookie httpOnly bienetre_session)
SPA vanilla JS · design tokens : « sage » clair (#F5F9F6 fond, #0B8C7D sauge), fallbacks emerald/mystic
```

## 🔑 Comptes démo + codes

| Rôle | Email | Mot de passe |
|---|---|---|
| Superadmin (coach CDB) | `charles@cdb-hub.app` | `Rosemary2026!` |
| Élève démo | `demo@cdb-hub.app` | `Demo2026!BienLms` |

Codes actifs : `BLW-BIEN-2026` (F1) · `BLW-DEPART` (F1) · **`BLW-PACK-FULL`** (pack = F1+F2+F3)

## 🚀 Démarrage

```bash
cd cdb-bienetre-lms
python3 db.py      # 21 tables
python3 seed.py    # école bienetre + comptes + 3 parcours + pack + codes
python3 server.py  # http://localhost:51840
BASE=http://localhost:51840 bash test_e2e.sh   # 27 étapes — tout vert
```

## 📦 Design system

Palette claire « sage » adaptée du teal Teachizy (#32C4C0) : fond `#F5F9F6`, cartes `#FFFFFF`,
accent `#0B8C7D`, or `#B98A2F`, radius 18px, Poppins. Le superadmin hérite de l'école par défaut
(fix : `/api/me` renvoie l'école bienetre même sans `school_id`).

---
*Fork Rosémary LMS v1.0 (Builder BL, flotte CDB HUB) — v2 octobre 2026.*
