#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_data.py — LMS Bien-Être (fork Rosémary v2)
Données initiales : école "bienetre" + 3 formations de l'accompagnement:
F1 Kit de décarrage (gratuit), F2 Remplir son agenda (397 €), F3 Système complet (997 €).
Prix type du positionnement CDB accompagnement. Idempotent par slug.
"""
import json

def Q(w, o, ok, ex):
    return {"question": w, "options": o, "correct": ok, "explanation": ex}

QUIZ_M1_F1 = [
    Q("Quelle est la première action du Kit de démarrage ?",
      ["Créer sa page de réservation", "Clarifier son offre en une phrase", "Lancer des publicités", "Acheter un site web"],
      1, "On clarifie d'abord l'offre : une phrase, une promesse, un public. Tout le reste en découle."),
    Q("Un praticien bien-être doit surtout…",
      ["vendre des séances", "résoudre un problème précis pour un public précis", "être actif sur 5 réseaux", "baisser ses prix"],
      1, "La clarté de la promesse (problème → public → résultat) fait 80 % de la vente."),
    Q("Qu'est-ce qu'un « avatar client » ?",
      ["Un logo", "Le portrait précis de son client idéal", "Un avatar de jeu vidéo", "Une fiche comptable"],
      1, "L'avatar client décrit qui tu aides, son problème, ses mots, ses freins."),
    Q("La première preuve à collecter est…",
      ["un certificat", "un témoignage client écrit ou vidéo", "un abonnement Instagram", "un diplôme d'école de commerce"],
      1, "Un témoignage vaut plus que 10 posts : il rassure les futurs clients."),
]

QUIZ_M2_F1 = [
    Q("Combien de temps d'avance faut-il pour annoncer un atelier ?",
      ["4 à 6 semaines", "1 jour", "2 heures", "6 mois"],
      0, "4 à 6 semaines : assez pour remplir, assez court pour l'anticipation."),
    Q("Le meilleur moment pour demander un avis est…",
      ["à froid 6 mois après", "juste après une belle séance", "quand on a un doute", "jamais"],
      1, "À chaud, la satisfaction est maximale : c'est le bon moment, avec consentement."),
    Q("Une relance polie à un prospect qui n'a pas répondu doit…",
      ["accuser de l'inviser", "apporter une valeur en plus (réponse courte + ressource)", "être longue et détaillée", "être envoyée 10 fois"],
      1, "La relance utile : « je te partage ceci au cas où » — jamais de culpabilisation."),
    Q("Carte cadeau : son vrai rôle est…",
      ["réduire les marges", "transformer un client satisfait en prescripteur", "remplacer une séance", "attirer les curieux uniquement"],
      1, "La carte cadeau fait entrer des nouveaux clients par le canal de confiance : un proche."),
]

QUIZ_M1_F2 = [
    Q("Le meilleur canal de démarrage d'un praticien, c'est…",
      ["Instagram", "le bouche-à-oreille structuré", "YouTube", "Pinterest"],
      1, "On structure d'abord le bouche-à-oreille (avis, parrainage, cartes) avant de scaler en ligne."),
    Q("Une page de réservation doit contenir…",
      ["10 paragraphes sur sa vie", "offre claire + tarifs + créneaux + témoignages", "un formulaire à 20 champs", "un livre PDF obligatoire"],
      1, "Simple, scannable en 10 secondes : quoi, pour qui, combien, comment réserver."),
    Q("Pourquoi limiter le nombre de créneaux affichés ?",
      ["pour paraître occupé", "pour créer une saine rareté et protéger son énergie", "c'est interdit", "pour éviter les impôts"],
      1, "L'agenda protégé = énergie durable ET vraie valeur perçue."),
    Q("Le prix d'une séance doit être…",
      ["le plus bas du marché", "justifié par le résultat et annoncé sans hésiter", "négociable par SMS", "caché jusqu'au RDV"],
      1, "Prix annoncé clairement = client arrivé avec le bon niveau d'engagement."),
]

QUIZ_M2_F2 = [
    Q("Un e-mail de relance à un client inactif doit…",
      ["culpabiliser", "offrir une raison concrète de revenir", "dévaluer les concurrents", "être envoyé à 3 h du matin"],
      1, "Une nouvelle utile, une invitation simple, zéro guilt."),
    Q("Le meilleur moment pour montrer « à quoi ça ressemble » ?",
      ["après le paiement", "avendre : photos/sons/ambiance du cabinet", "jamais", "seulement en présentiel"],
      1, "On réduit l'inquiétude de « l'inconnu » en montrant l'expérience du cabinet."),
    Q("La séquence idéale pour un nouveau contact est…",
      ["post → DM → page → appel → séance", "appel direct sans annonce", "annonce payante → séance", "email → séance"],
      0, "Chaîne de confiance : le contenu attire, la conversation qualifie, la page convertit."),
    Q("Combien d'offres différentes viser au départ ?",
      ["Une offre principale, une seconde si besoin", "huit offres", "aucune offre définie", "des offres au cas par cas"],
      0, "Dès le départ : une offre phare claire. Les « expériences » et ateliers viennent après."),
]

QUIZ_M1_F3 = [
    Q("Le rôle d'un tableau de bord simple est…",
      ["faire joli", "montrer CA, réservations d'avance et remplissage", "remplacer le comptable", "suivre les likes"],
      1, "Trois chiffres suffisent : CA du mois, séances réservées à venir, taux de remplissage de l'agenda."),
    Q("« Remplissage agenda » veut dire…",
      ["nombre d'heures travaillées", "séances réservées / créneaux ouverts", "heures de sommeil", "le nombre de posts"],
      1, "Creneaux ouverts sur le mois ÷ séances réservées = ton pouls commercial."),
    Q("Un bon pipeline client contient…",
      ["les leads, les RDV proposés, les payés, les terminés", "uniquement les payés", "les noms des concurrents", "les followers"],
      0, "Voir les étapes = savoir où intervenir (relance, appel, rappel de paiement)."),
    Q("Quand remplit-on le tableau de bord ?",
      ["une fois par an", "chaque semaine, 10 minutes", "quand ça va mal", "chaque heure"],
      1, "Rituel hebdomadaire de 10 minutes : on regarde, on décide, on agit."),
]

QUIZ_M2_F3 = [
    Q("Automatiser, c'est…",
      ["perdre le contact humain", "déléguer les tâches répétitives (rappels, relances)", "mentir aux clients", "payer plus d'impôts"],
      1, "Ton temps précieux va au soin : la machine gère la répétition."),
    Q("Un bon message de rappel RDV est…",
      ["long et officiel", "court, avec lien de report en 1 clic", "envoyé par la secrétaire imaginaire", "sans émoji"],
      1, "Rappel à J-1 + lien de report : moins d'oublis, moins de trous dans l'agenda."),
    Q("Le contenu qui convertit le mieux pour un praticien est…",
      ["des mèmes tendance", "des réponses aux vraies questions des clients (contenu utile)", "des citations génériques", "des posts sur la concurrence"],
      1, "Le contenu « réponse » : chaque question client devient une séance de contenu."),
    Q("La marque blanche (sous ton domaine) sert à…",
      ["diviser le site", "offrir ton espace de cours à TON image et ta couleur", "payer moins d'hébergement", "copier les autres"],
      1, "L'espace élève porte la marque du praticien — cohérence premium."),
]

ALL_COURSES = [
    {
        "slug": "kit-demarrage",
        "title": "F1 — Kit de démarrage du praticien",
        "subtitle": "Pose en 7 jours les bases vendables : offre claire, tarifs justifiés, premiers témoignages",
        "desc": "<p>Le kit que tout praticien bien-être accompagné démarre par là. En sept leçons courtes, tu poses "
                "les fondations commerciales : ton offre en une phrase, ton client idéal, tes tarifs annoncés avec "
                "sérénité et tes premiers témoignages.</p><p>Chaque leçon se termine par une <strong>action de 15 "
                "minutes</strong> : on avance par la pratique, pas par la théorie.</p>",
        "level": "débutant", "price": 0, "old_price": None, "duration": "7 jours · 7 leçons courtes",
        "color": "#0B8C7D",
        "modules": [
            {"title": "Module 1 — Clarifier ton offre",
             "desc": "Une phrase claire qui fait dire « c'est exactement ça ».",
             "quiz": 3,
             "lessons": [
                 {"title": "Ta promesse en une phrase", "video": True, "free": True,
                  "html": "<p>Beaucoup de praticiens décrivent leur métier ; presque personne ne décrit son <strong>résultat</strong>...</p>"},
                 {"title": "Ton client idéal (avatar)", "video": False, "free": False,
                  "html": "<p>Qui viens-tu réellement aider ? Dresse son portrait en 6 questions...</p>"},
                 {"title": "Ton positionnement en 3 mots", "video": False, "free": False,
                  "html": "<p>Trois mots choisis deviennent ta boussole de contenu...</p>"},
                 {"title": "Action — écris ta phrase magique", "video": False, "free": False,
                  "html": "<p>À faire : 5 phrases possibles, tu gardes celle qui colle le plus, on l'affine ensemble en coaching.</p>"},
             ]},
            {"title": "Module 2 — Tes premières preuves",
             "desc": "Témoignages, avis et cartes cadeaux : transformer l'estime en visibilité.",
             "quiz": 3,
             "lessons": [
                 {"title": "Récolter un témoignage (script de demande)", "video": True, "free": False,
                  "html": "<p>Le script de demande en 4 phrases…</p>"},
                 {"title": "La carte cadeau bien faite", "video": False, "free": False,
                  "html": "<p>Une carte cadeau = un nouveau client introduit par un proche…</p>"},
                 {"title": "Devenir réferrable : après-séance", "video": False, "free": False,
                  "html": "<p>Le mini-rituel de fin de séance qui rend naturel le partage…</p>"},
                 {"title": "Action — 3 demandes envoyées", "video": False, "free": False,
                  "html": "<p>À faire : envoyer ta demande de témoignage à 3 clients satisfaits (les bons, pas les plus proches).</p>"},
             ]},
        ],
    },
    {
        "slug": "remplir-son-agenda",
        "title": "F2 — Remplir son agenda en continu",
        "subtitle": "Le système de réservation, du bouche-à-oreille structuré à l'agenda qui déborde",
        "desc": "<p>Le système que l'on installe pour que l'agenda se remplisse sans épuisement : canal par canal, "
                "de la page de réservation aux relances utiles, jusqu'aux ateliers qui attirent.</p>",
        "level": "intermédiaire", "price": 397, "old_price": 597, "duration": "21 jours",
        "color": "#1BA098",
        "modules": [
            {"title": "Module 1 — Le système de réservation",
             "desc": "L'embouteillage : de la première impression à la séance payée.",
             "quiz": 3,
             "lessons": [
                 {"title": "Ta page de réservation (structure exacte)", "video": True, "free": True,
                  "html": "<p>La structure en 5 blocs qui convertit…</p>"},
                 {"title": "Le bon-à-savoir des créneaux", "video": False, "free": False,
                  "html": "<p>Protéger son énergie par la limitation saine…</p>"},
                 {"title": "Du premier contact à la séance payée", "video": False, "free": False,
                  "html": "<p>La chaîne de confiance en 5 étapes…</p>"},
                 {"title": "Action — ta page en ligne", "video": False, "free": False,
                  "html": "<p>À faire : publier ta page de réservation (même simple) et la faire lire à 2 proches.</p>"},
             ]},
            {"title": "Module 2 — Les relances qui font revenir",
             "desc": "Relances utiles = clients réactivés sans pression.",
             "quiz": 3,
             "lessons": [
                 {"title": "La relance à froid qui n'accable pas", "video": True, "free": False,
                  "html": "<p>Le format 3 phrases…</p>"},
                 {"title": "Séquence « montre-moi ton cabinet »", "video": False, "free": False,
                  "html": "<p>Réduire l'inconnu…</p>"},
                 {"title": "Rappeler après l'abandon", "video": False, "free": False,
                  "html": "<p>Quand un prospect disparaît au milieu du tunnel…</p>"},
                 {"title": "Action — ta séquence de relance", "video": False, "free": False,
                  "html": "<p>À faire : écrire tes 2 messages de relance réutilisables et les sauvegarder en note.</p>"},
             ]},
        ],
    },
    {
        "slug": "systeme-complet",
        "title": "F3 — Le système complet du praticien",
        "subtitle": "Tableau de bord, pipeline, automatisation et marque : l'agenda et le CA prennent soin de toi",
        "desc": "<p>Niveau avancé de l'accompagnement : on installe le tableau de bord, le pipeline client, les "
                "automatisations de relance et l'espace élève à ta marque — pour que ton activité tienne debout sans toi chaque semaine.</p>",
        "level": "expert", "price": 997, "old_price": None, "duration": "6 semaines",
        "color": "#2BC0AD",
        "modules": [
            {"title": "Module 1 — Piloter son activité",
             "desc": "Trois chiffres hebdomadaires et un rituel de 10 minutes.",
             "quiz": 3,
             "lessons": [
                 {"title": "Ton tableau de bord en 3 chiffres", "video": True, "free": True,
                  "html": "<p>CA, remplissage, séances à venir…</p>"},
                 {"title": "Ton pipeline client visuel", "video": False, "free": False,
                  "html": "<p>Le tableau à 4 colonnes…</p>"},
                 {"title": "Le rituel hebdo de 10 minutes", "video": False, "free": False,
                  "html": "<p>Regarde, décide, agit…</p>"},
                 {"title": "Action — installe ton rituel", "video": False, "free": False,
                  "html": "<p>À faire : bloquer 10 minutes récurrentes dans ton agenda, avec les 3 questions imprimées.</p>"},
             ]},
            {"title": "Module 2 — Automatiser et se marquer",
             "desc": "Faire tourner l'essentiel pendant que tu soignes.",
             "quiz": 3,
             "lessons": [
                 {"title": "Les relances automatiques utiles", "video": True, "free": False,
                  "html": "<p>Rappel RDV à J-1…</p>"},
                 {"title": "Ton contenu « réponse »", "video": False, "free": False,
                  "html": "<p>Chaque question client devient un contenu…</p>"},
                 {"title": "Ton espace élève à ta marque", "video": False, "free": False,
                  "html": "<p>Marque blanche : couleurs, logo, ton espace…</p>"},
                 {"title": "Action — ton premier automatisme", "video": False, "free": False,
                  "html": "<p>À faire : activer UN rappel RDV automatique cette semaine (pas cinq — un seul, bien fait).</p>"},
             ]},
        ],
    },
]
