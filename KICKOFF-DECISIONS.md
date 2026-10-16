# KICKOFF-DECISIONS — SaaS LMS Numérologie (projets CDB HUB)
## Date : 2026-10-01 · Auteur : Builder (BL) · En attente du GO de Charles

---

## 1. Ce que j'ai compris du brief

| Point | Compréhension |
|---|---|
| Produit | Un **SaaS LMS (Learning Management System)** dédié aux formations en numérologie |
| Contenus | Sur Google Drive (charles.doebruce@gmail.com) : fichiers de **décomposition des formations en modules** + **tout le contenu de la formation**. Token OAuth à regénérer (non authentifié sur ce profil) |
| Design | S'inspirer de https://helium-template.framer.website/ : **dark premium** (noir, émeraude, Poppins) |
| Évolutivité | Aujourd'hui **supports écrits** ; demain **vidéos** pour chaque module et chaque cours |
| Exigence | Beau visuellement, facile d'usage, ergonomique |
| Benchmark | Fonctionnalités des meilleurs LMS : **Teachizy, Podia** |
| Process | Architecture D'ABORD, validation de Charles, PUIS build |

---

## 2. Design system extrait du site Helium (validé au navigateur + capture)

| Token | Valeur | Usage |
|---|---|---|
| Fond principal | `#000000` noir pur | Toutes les pages |
| Fond cartes / sections | `#0A0A0A` → `#121212` | Cartes de cours, blocs |
| Bordures | `#1E1E1E` subtile | Cartes, séparateurs |
| Texte principal | `#FFFFFF` | Titres, contenu |
| Texte secondaire | `rgba(255,255,255,0.62)` | Descriptions, labels |
| Accent primaire | **Vert émeraude lumineux** `#2DE28E` (logo + sphères glow) | Badges, CTA, progression |
| Boutons | Pill blanc (bg `#FFFFFF`, texte noir, radius 999px) | CTA principaux |
| Navigation | Pill flottante translucide, centrée | Nav desktop |
| Typographie | **Poppins** (600/700 titres, 400 corps, italique pour les citations) | Tout le site |
| Effets signature | Grandes **sphères 3D émeraude avec glow flouté** en fond | Hero, sections |
| Composants récurrents | Eyebrow (label en petites capitales) au-dessus des titres · cartes radius ~18px · vignettes dégradées colorées · **statistiques géantes** (40%, 70%) · marquee de logos | Landing + app |

### Proposition d'adaptation numérologie
Palette Helium conservée **intégralement** (fidélité à la référence). La couleur d'accent reste l'émeraude — option offerte : variante « mystique » (violet améthyste `#8B5CF6` + or `#D4A843`) qui colle au thème numérologie. **Décision à Charles.**

---

## 3. Architecture fonctionnelle

### Rôles
- **Admin (Charles)** : tout, builder de cours, étudiants, stats
- **Étudiant** : ses formations, progression, quiz, certificat

### Périmètre MVP (inspiré Teachizy / Podia)

**Public (vitrine de vente)**
1. Landing Helium-style : hero (« Maîtrisez l'art de la numérologie »), promesse, preuves sociales, catalogue des formations, FAQ, CTA
2. Page formation détaillée : programme complet (modules → leçons), infos prix/durée, extrait gratuit
3. Catalogue + inscription/connexion

**Espace Étudiant**
4. Dashboard « Mes formations » avec progression continue
5. Espoir de cours : sidebar modules/leçons (collapsée), leçon courante, **bouton « Marquer comme terminée »**, barre de progression, navigation précédent/suivant
6. **Lecteur de contenu** : texte riche (HTML), support PDF téléchargeable, **emplacement vidéo réservé** (placeholder élégant « Vidéo à venir » — branchable en 1 champ plus tard)
7. **Quiz** : QCM interactifs en fin de module, score, correction expliquée
8. **Drip content** : libération progressive optionnelle des modules (J+n)
9. **Certificat de fin de formation** : généré si 100% + quiz réussi (PDF avec n° de série)

**Espace Admin**
10. **Course builder** : CRUD formations → modules → leçons (éditeur texte riche, upload PDF, champ URL vidéo ready)
11. Gestion étudiants : liste, progression par formation, relance
12. Stats : inscriptions, taux de complétion, leçons populaires
13. Annonces par formation (mur d'infos étudiant)
14. Réglages branding

### Monétisation (V-MVP, proposition)
- V1 : **Activation manuelle/code d'accès** (codes premium générés par l'admin, chaque code = 1 formation) — zéro friction, pas de dépendance
- V2 : **Stripe Checkout** intégré (pattern déjà éprouvé sur la flotte CDB)

---

## 4. Architecture technique

### Stack (pattern CDB vertical — identique aux verticales en prod)
- **Backend** : Python 3 stdlib `BaseHTTPRequestHandler` (server.py, ~port **51810**), SQLite `db.py` (WAL, 1 connexion/requête), auth `auth.py` (bcrypt + cookie httpOnly), seed `seed_drive.py`
- **Frontend** : SPA vanilla JS (`static/app.js`, une `viewX()` par page) + `design-tokens.css` (tokens Helium ci-dessus). Sans build tooling, cache-busting `?v=x.y`
- **Contenus** : ingestion Drive → conversion automatique des supports (dév des modules + contenu complet) en leçons HTML ; PDF servis par le serveur ; images hébergées en local
- **Vidéos** : champ `video_url` dès V1 sur chaque leçon (placeholder « à venir » tant que vide) — branchable YouTube/Vimeo/Mux sans refonte
- **Déploiement** : VPS srv1676946 + tunnel Cloudflare (`lms.cdb-hub.app` → 51810) + extension du watchdog 120 s + repo GitHub `charlescdbhub-beep/*` + README
- **Multi-tenant** : `user_id`/tables métier propres ; V1 = **mono-école (celle de Charles)** avec `tenant_id` prévu dans le schéma si l'outil doit un jour être revendu à d'autres formateurs

### Schéma de données (tables)
`users` (admin/student) · `courses` (slug, prix, statut draft/published) · `modules` (course_id, position) · `lessons` (module_id, type text/video/pdf/quiz, content_html, video_url, position, free_preview, drip_days) · `enrollments` (user/course, source, code) · `access_codes` (code, course, usage) · `progress` (user/lesson, completed_at) · `quizzes` + `quiz_questions` (options, index correct, explication) · `certificates` (série) · `announcements` · `settings`

### Pages publiques ↔ app
- `landing.html` (visiteur) → login/signup → `/app` (étudiant) ; session admin → bâtiment admin
- Pattern éprouvé : la landing est servie sur la racine, session active = redirect `/app`

---

## 5. Plan de livraison (phases, dans l'ordre)

| # | Phase | Contenu | Preuve livrée |
|---|---|---|---|
| 0 | **Token Drive** | Guidage OAuth (je génère le lien, tu autorises, je colle le code) ; lecture du dossier numérologie | Liste des fichiers/modules détectés |
| 1 | Fondation | db.py + server.py + auth.py + tokens CSS Helium | Test smoke |
| 2 | Landing publique | Hero, preuves, catalogue, FAQ (style Helium) | Capture navigateur |
| 3 | Admin + builder | CRUD complet formations/modules/leçons + étudiants + stats | Capture de chaque onglet |
| 4 | Espace étudiant | Cours + progression + quiz + certificat + drip | Parcours E2E complet |
| 5 | **Ingestion Drive** | Téléchargement + conversion des contenus réels en leçons | Contenus visibles dans l'app |
| 6 | Déploiement | Port 51810 + tunnel `lms.cdb-hub.app` + watchdog 7 services + GitHub/README | URL publique + captures |
| 7 | Compte démo | Seed étudiant démo (identifiants affichés) + recharge pattern | Identifiants dans le bilan |

**Décisions validées par Charles (01/10/2026) :**
- **Nom : « Rosémary — École de Numérologie »** (littéral tapé : "rosemary Ecole de Numérologie")
- **Accent : les deux — émeraude par défaut + toggle « mystique » (violet améthyste + or)**
- **Activation : multi-échelle — MULTI-ÉCOLE dès V1** (schéma tenant_id sur toutes les tables ; chaque formateur peut créer son école, Charles = super-admin)
- **Port 51810 · lms.cdb-hub.app · Stripe en V2** (V1 multi-école passe par un prix affiché + activation manuelle/code par l'école)

## Décisions notées (voir §5 pour le plan)
GO implicite reçu : cadrage + 4 réponses claires → GO pour toute la mission (nuance playbook), livraison en une vague avec bilan final tableau adresses/identifiants.

---

## 6. Inputs bloquants / à fournir

1. **GO** sur architecture + décisions ci-dessus
2. **Token Drive** (phase 0) — OAuth guidé, ~5 min
3. Nom du produit si autre que « Numéra »
4. Prix des formations (affichés sur la landing et la page formation)