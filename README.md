# Optiport

Plateforme d'allocation d'ETF : prévision de rendement par LSTM (un modèle par
ticker) et optimisation moyenne-variance, exposées dans une interface de type
terminal de marché.

---

## Démarrage

Deux processus sont nécessaires : le backend FastAPI (modèle, optimiseur,
authentification et base de données) et l'interface Streamlit.

```bash
python -m uvicorn api:app --reload --port 8000
```

```bash
streamlit run app.py
```

L'interface est disponible sur <http://localhost:8501>, l'API sur
<http://localhost:8000> (documentation interactive sur `/docs`).

> Le point d'entrée est `app.py`. L'ancien `streamlit_app.py` — l'interface
> d'origine en un seul fichier — a été supprimé lors de la refonte.

> **Le backend est requis dès l'écran de connexion** : contrairement aux
> versions antérieures, il n'y a plus de mode "session anonyme" — l'inscription,
> la connexion et l'intégralité du portefeuille simulé (positions, ordres,
> transactions, watchlist, alertes) vivent en base de données côté backend.
> Sans backend accessible, l'écran de connexion affiche un message d'erreur
> explicite ; une fois connecté, seules l'optimisation, les prévisions et la
> frontière efficiente restent tolérantes à une coupure temporaire du backend
> (l'interface l'indique explicitement sur les pages concernées).

### Premier démarrage — créer le compte administrateur

Aucun mot de passe n'est codé en dur : le premier compte administrateur se
crée via une commande dédiée, qui lit les identifiants dans l'environnement
ou les demande de façon interactive (mot de passe masqué, jamais journalisé) :

```bash
python -m backend.create_admin
```

Voir [Authentification & autorisation](#authentification--autorisation)
ci-dessous pour le détail des variables d'environnement.

### Dans VS Code

Ouvrez le dossier `Optiport` (et non le dossier parent) dans VS Code, puis :

- **F5** → « ▶ Optiport (API + Interface) » lance les deux serveurs en même
  temps, avec le débogueur. Arrêter la session arrête les deux.
- Ou **Terminal → Exécuter la tâche… → « Optiport : démarrer tout »** pour les
  lancer sans débogueur.

Les fichiers `.vscode/` fournissent ces configurations et pointent
automatiquement sur l'environnement virtuel `venv/`. L'extension **Python** de
Microsoft doit être installée (elle fournit le débogueur pour le F5).

---

## Architecture

```
app.py                  Point d'entrée : configuration, contexte partagé, navigation
├── ui/                 Design system (aucune logique métier)
│   ├── tokens.py       Palettes, échelles d'espacement, rayons, ombres, couleurs sémantiques
│   ├── styles.py       Génération des variables CSS + injection de la feuille de style
│   ├── format.py       Formatage monétaire, pourcentages, dates, durées relatives
│   ├── icons.py        Material Symbols — un seul jeu d'icônes pour toute l'application
│   ├── components.py   Cartes, KPI, tableaux, chips, sparklines, états vides/erreur…
│   ├── charts.py       Fabriques Plotly préconfigurées au thème
│   ├── layout.py       Sidebar, topbar, en-têtes de page, notifications
│   └── assets/         app.css, logo.svg, logo-mark.svg
├── services/           Accès aux données (aucune présentation)
│   ├── catalog.py      Univers ETF : secteurs, régions, thèmes, couleurs
│   ├── market.py       Yahoo Finance : cotations, historiques, signaux, actualités
│   ├── api_client.py   Client HTTP du backend (auth + portefeuille + prévisions), erreurs typées
│   ├── store.py        État de session : cache du portefeuille backend, préférences UI
│   ├── analytics.py    Mesures de risque et de performance calculées pour l'affichage
│   └── context.py      Contexte partagé, résolu une fois par exécution
├── views/              Une page = un module (exécuté à la demande)
│   ├── auth.py         Écran de connexion / inscription (non authentifié)
│   └── admin.py        Tableau de bord administrateur (visible aux admins uniquement)
├── api.py              API FastAPI — inclut les routers backend/routers/
└── backend/
    ├── forecaster.py   Features, LSTM, rendements attendus, covariance
    ├── optimizer.py    Optimisation SLSQP, frontière efficiente, recommandations
    ├── db.py            Moteur SQLAlchemy, session, bootstrap du schéma
    ├── models.py        Modèles ORM : users, accounts, positions, orders, transactions,
    │                    watchlist_items, alerts, token_blocklist
    ├── security.py      Hachage bcrypt, émission/vérification des JWT
    ├── deps.py          Dépendances FastAPI : get_current_user, require_admin
    ├── schemas.py        Modèles Pydantic auth/admin/portefeuille
    ├── crud.py          Opérations base de données, moteur d'exécution des ordres
    ├── pricing.py        Cours de marché faisant foi côté serveur (yfinance)
    ├── create_admin.py   CLI : python -m backend.create_admin
    └── routers/
        ├── auth.py       /auth/register, /auth/login, /auth/logout, /auth/me
        ├── admin.py      /admin/users, /admin/stats
        └── portfolio.py  /portfolio/* — compte, positions, ordres, transactions, watchlist, alertes
```

### Principes

- **Le calcul et les mutations de compte restent au backend.** L'interface
  n'implémente ni prévision, ni optimisation, ni exécution d'ordre : elle
  appelle `/smart-invest`, `/forecast`, `/chart-data`, `/efficient-frontier`
  et, depuis l'ajout de l'authentification, `/portfolio/*` pour tout ce qui
  touche au compte simulé. `services/analytics.py` ne contient que des
  mesures d'affichage (volatilité, Sharpe, drawdown, corrélations, attribution).
- **Une seule source de vérité par donnée.** Les cotations sont récupérées en
  un appel par exécution, mises en cache, puis partagées via `services/context.py` ;
  le portefeuille (positions, ordres, transactions, watchlist, alertes) suit le
  même principe via `services/store.py::sync_portfolio()`.
- **Séparation stricte** entre `ui/` (présentation), `services/` (données) et
  `views/` (composition). Aucune vue ne fait d'appel réseau direct.
- **Chargement à la demande.** Chaque page est un script déclaré via
  `st.Page` : seule la page active s'exécute.

---

## Pages

| Section | Page | Contenu |
| --- | --- | --- |
| Pilotage | Dashboard | Valorisation, P&L, score de risque, performance vs indice, allocation, activité |
| | Markets | Tableau de marché complet, détail par instrument (chandeliers, rendements glissants, profil technique) |
| | Portfolio | Positions valorisées, allocation, attribution du P&L, mesures de risque, drawdown |
| | Watchlist | Suivi personnalisé en cartes ou tableau, avec actions par instrument |
| Exécution | Trading | Optimiseur (univers, profil, montant), résultats, comparaison aux pairs, plan de rééquilibrage, ordre manuel |
| | Orders | Carnet d'ordres, annulation des ordres en attente, historique filtrable |
| | Transactions | Journal des mouvements, flux par instrument, export CSV |
| Intelligence | News | Actualités Yahoo Finance des instruments suivis |
| | News Analysis | Sentiment financier (FinBERT), impact de marché, agrégation du jour, comparaison Base Forecast / News-Context Forecast |
| | Analytics | Frontière efficiente, corrélations, risque/performance, prévisions vs réalisé |
| | Alerts | Seuils de prix, alertes déclenchées, surveillance des signaux |
| Compte | Settings | Apparence, backend, valeurs par défaut, maintenance |
| | Profile | Identité, activité, préférences, sécurité |
| | Logout | Récapitulatif de session et déconnexion |
| Administration¹ | Admin | Liste des utilisateurs, rôles, activation/désactivation, suppression, statistiques système |

¹ Section visible uniquement pour un compte administrateur — voir
[Authentification & autorisation](#authentification--autorisation).

---

## Ce qui est réel, ce qui est simulé

L'interface distingue systématiquement les deux :

| Élément | Nature |
| --- | --- |
| Cours, historiques, volumes, actualités | **Réels** — Yahoo Finance via `yfinance` |
| Prévisions, poids optimisés, frontière efficiente | **Réels** — calculés par le backend |
| Signaux techniques (Strong Buy → Avoid) | **Calculés** — indicateur composite documenté dans l'interface, non prédictif |
| Comptes, positions, ordres, transactions, watchlist, alertes | **Persistés** en base (SQLite), propres à chaque utilisateur — mais l'exécution des ordres reste **simulée** (paper trading, aucun ordre transmis à un courtier) |
| Prix d'exécution des ordres | **Réels** au moment du remplissage — récupérés par le backend (jamais fournis par le client, voir plus bas) |

Le compte de démonstration est doté de 250 000 $. Les ordres au marché sont
servis au dernier cours connu, les ordres à cours limité lorsque le cours
franchit le seuil (évalué à chaque chargement de page, côté backend).

---

## Authentification & autorisation

### Architecture

- **Mots de passe** : hachés avec `bcrypt` (jamais stockés ni journalisés en
  clair). Aucune route ne renvoie `password_hash`.
- **Sessions** : tokens JWT (HS256), signés avec `AUTH_SECRET_KEY`. Le payload
  ne contient que l'identité (`sub`, `jti`, `exp`) — le rôle et le statut
  actif/désactivé ne sont **jamais** lus depuis le token : `backend/deps.py`
  les relit en base à chaque requête. Concrètement, désactiver un compte ou
  changer son rôle prend effet immédiatement, même sur un token non expiré.
- **Déconnexion réelle** : `POST /auth/logout` place le `jti` du token dans
  `token_blocklist` — le token est révoqué côté serveur, pas seulement
  oublié côté client. Un token révoqué est rejeté même s'il n'a pas encore
  expiré.
- **Toutes les routes exigent un token valide**, à l'exception de
  `/auth/register`, `/auth/login` et `/health` (sonde de connectivité utilisée
  avant même la connexion). Les routes `/admin/*` exigent en plus le rôle
  `admin`, revérifié côté serveur à chaque appel — jamais déduit d'un
  indicateur envoyé par le client.
- **Isolation des données** : chaque requête sur `/portfolio/*` est filtrée
  par l'`account_id`/`user_id` de l'appelant. Une ressource appartenant à un
  autre utilisateur (ordre, alerte…) renvoie `404`, pas `403`, pour ne pas
  révéler son existence.
- **Prix d'exécution faisant foi côté serveur** : un ordre au marché n'est
  jamais rempli au prix envoyé par le client — le backend récupère lui-même
  le dernier cours via `yfinance` (`backend/pricing.py`) avant de valider le
  remplissage.
- **Streamlit** : le token et le profil utilisateur vivent dans
  `st.session_state`, attachés automatiquement comme `Authorization: Bearer
  <token>` par `services/api_client.py`. Cela survit à la navigation entre
  pages (une même session Streamlit), mais **pas à un rafraîchissement complet
  du navigateur ou à un nouvel onglet** — Streamlit n'offre pas de stockage en
  cookie sans composant tiers ; c'est une limite connue et assumée plutôt que
  contournée par une dépendance supplémentaire.

### Schéma de base de données (SQLite, `backend/models.py`)

```
users            1───1  accounts (cash simulé)
                          │
                          ├──* positions   (ticker, quantité, prix moyen)
                          ├──* orders      (sens, quantité, type, statut, prix d'exécution…)
                          └──* transactions
users            1───*  watchlist_items
users            1───*  alerts
                  *  token_blocklist (jti des tokens révoqués)
```

Chaque table appartenant à un utilisateur porte une clé étrangère indexée
vers son propriétaire, avec suppression en cascade (`ondelete=CASCADE`) :
supprimer un utilisateur supprime proprement tout ce qui lui appartient.

Décisions volontairement écartées :
- **Pas de table dédiée aux prévisions/actualités** : elles restent calculées
  à la demande et mises en cache en mémoire (`backend/news_cache.py`), comme
  avant — les persister dupliquerait ce mécanisme sans bénéfice net pour une
  donnée qui n'appartient à personne en particulier.
- **Pas de vue admin sur le portefeuille d'un utilisateur** : un administrateur
  gère les comptes (rôle, activation, suppression) mais n'a pas d'endpoint
  pour consulter les positions/ordres d'un autre utilisateur — choix du
  moindre privilège, à revoir explicitement si un usage l'exige.

### Migrations

Il n'existait aucune donnée persistante avant cette fonctionnalité (tout
vivait dans `st.session_state`, perdu au redémarrage) : il n'y a donc rien à
migrer. `Base.metadata.create_all()` (appelé au démarrage du backend, voir le
`lifespan` dans `api.py`) crée le schéma s'il n'existe pas encore et ne touche
jamais aux tables existantes — sûr à ré-exécuter à chaque démarrage. Si le
schéma évolue significativement à l'avenir, un outil de migration dédié
(Alembic) devient pertinent ; il n'a pas été introduit ici pour ne pas
sur-outiller un schéma qui n'a encore aucune donnée à préserver.

### Variables d'environnement (`.env`, voir `.env.example`)

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `AUTH_SECRET_KEY` | Clé de signature des JWT | Générée aléatoirement au démarrage si absente — **tous les tokens deviennent invalides au redémarrage** ; à définir explicitement dès qu'on veut des sessions stables |
| `AUTH_TOKEN_EXPIRE_MINUTES` | Durée de vie d'un token | `480` (8 h) |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///<racine du repo>/optiport.db` |
| `NEWS_API_KEY` | Clé NewsAPI (module News/Sentiment) | — |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_FULL_NAME` | Bootstrap du premier admin (voir ci-dessous) | Demandés de façon interactive si absents |

### Créer le premier compte administrateur

```bash
python -m backend.create_admin
```

Sans variables d'environnement, la commande demande le nom d'utilisateur,
l'e-mail et le mot de passe de façon interactive (saisie masquée via
`getpass`, jamais journalisée). Avec les variables `ADMIN_*` définies, elle
s'exécute sans interaction — pratique pour un déploiement scripté. Elle
refuse d'écraser un compte existant : pour promouvoir un compte déjà créé via
l'interface, passez par `PATCH /admin/users/{id}` une fois un premier admin
en place.

### Permissions par défaut

| Action | Utilisateur | Administrateur |
| --- | --- | --- |
| Consulter le marché, les prévisions, les actualités | ✅ | ✅ |
| Gérer son propre portefeuille (ordres, watchlist, alertes) | ✅ | ✅ |
| Modifier son propre profil | ✅ | ✅ |
| Consulter le portefeuille d'un autre utilisateur | ❌ | ❌ (choix délibéré, voir plus haut) |
| Lister les utilisateurs, voir les statistiques système | ❌ | ✅ |
| Changer le rôle / activer / désactiver un utilisateur | ❌ | ✅ (sauf son propre compte) |
| Supprimer un utilisateur | ❌ | ✅ (sauf son propre compte) |

### API — endpoints ajoutés

| Méthode | Route | Rôle |
| --- | --- | --- |
| POST | `/auth/register` | Inscription — crée l'utilisateur, son compte simulé, retourne un token |
| POST | `/auth/login` | Connexion — retourne un token |
| POST | `/auth/logout` | Révoque le token courant |
| GET | `/auth/me` | Profil de l'utilisateur connecté |
| PATCH | `/auth/me` | Met à jour nom / fonction / desk |
| GET | `/admin/users` | Liste des utilisateurs *(admin)* |
| PATCH | `/admin/users/{id}` | Change le rôle / statut actif *(admin)* |
| DELETE | `/admin/users/{id}` | Supprime un utilisateur *(admin)* |
| GET | `/admin/stats` | Statistiques système *(admin)* |
| GET/POST | `/portfolio/account`, `/positions`, `/orders`, `/transactions`, `/watchlist`, `/alerts` | Compte simulé de l'utilisateur connecté, isolé par utilisateur |
| POST | `/portfolio/settle` | Règle les ordres à cours limité et les alertes contre les cours actuels |
| POST | `/portfolio/reset` | Réinitialise le compte simulé (conserve la watchlist) |

### Tests dédiés

```bash
pytest tests/test_auth.py tests/test_authorization.py tests/test_data_isolation.py
```

Couvrent l'inscription, les doublons, la connexion, `/auth/me`, la révocation
au logout, les comptes désactivés, la prise en compte immédiate d'un
changement de rôle sur un token déjà émis, le rejet des routes `/admin/*`
pour un utilisateur normal, et — le plus important — qu'un utilisateur ne
peut ni lire ni modifier les positions, ordres, transactions, watchlist ou
alertes d'un autre utilisateur (y compris par tentative d'IDOR sur un
identifiant deviné).

---

## Modèles LSTM

Le backend cherche les modèles dans
`trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs`
(`<TICKER>_model.keras` + `scalers.pkl`).

**En leur absence, il ne renvoie pas d'erreur** : il retombe sur le dernier
rendement observé à 22 séances, ce qui produit des prévisions annualisées très
volatiles (souvent bornées à −50 %). L'interface signale explicitement ce cas
sur les pages Trading et Analytics. Le chemin est configurable dans Settings.

---

## News, Sentiment & Market Impact

Pipeline complet, exécuté entièrement côté backend FastAPI :

```
NewsAPI (backend/news_service.py)
        ↓
Preprocessing (backend/news_preprocessing.py)
   HTML/entités retirés, texte tronqué nettoyé, doublons supprimés,
   articles trop courts écartés
        ↓
Sentiment (backend/sentiment.py)
   FinBERT (ProsusAI/finbert, poids TensorFlow) si `transformers` est
   installé et le modèle téléchargeable, sinon repli automatique sur un
   score lexical financier — jamais de crash, jamais de rechargement
   par requête (singleton process-wide)
        ↓
Market Impact (backend/market_impact.py)
   direction (POSITIVE/NEGATIVE/NEUTRAL) + niveau (LOW/MEDIUM/HIGH) +
   confiance, à partir du sentiment ET d'un score de matérialité déduit
   du type de nouvelle (résultats, M&A, régulation… vs mention générique)
        ↓
Recency weighting (backend/news_recency.py)
   décroissance exponentielle, demi-vie 6h
        ↓
Aggregation (backend/news_aggregator.py)
   sentiment pondéré, compteurs positif/négatif/neutre, impact global
        ↓
News Features (backend/news_features.py)
        ↓
Forecast Context (backend/forecast_context.py)
   Base Forecast = backend/forecaster.py (LSTM existant, inchangé)
   News-Context Forecast = Base Forecast + ajustement borné (±2 pt sur
   le rendement 22j), proportionnel à sentiment × impact × confiance
```

### Configuration

Créez `.env` dans `Optiport/` (déjà dans `.gitignore`) :

```env
NEWS_API_KEY=votre_clé_newsapi
```

`NEWS_API_KEY` n'est lu que par `backend/config.py` et `backend/news_service.py` :
il ne transite jamais vers l'interface Streamlit, n'apparaît dans aucune
réponse d'API ni aucun log.

### Endpoints

| Méthode | Route | Rôle |
| --- | --- | --- |
| POST | `/news/analyze` | Sentiment + impact pour un titre/contenu saisi manuellement |
| GET | `/news/{ticker}` | Actualités récentes du ticker, notées individuellement |
| GET | `/news/{ticker}/summary` | Agrégation du jour (compteurs, sentiment pondéré, impact global) |
| POST | `/forecast/context` | Base Forecast vs. News-Context Forecast |

### Limites

- Pas de persistance dédiée pour les actualités : elles sont mises en cache en
  mémoire process (~20 min, `backend/news_cache.py`), pas persistées entre
  redémarrages du backend — contrairement aux comptes/portefeuilles, qui eux
  sont en base (voir [Authentification & autorisation](#authentification--autorisation)).
- FinBERT télécharge ses poids depuis Hugging Face au premier appel ; sans
  réseau ou sans `transformers` installé, le repli lexical s'applique
  automatiquement (moins précis, mais toujours disponible).
- L'ajustement du forecast est une couche heuristique au-dessus du LSTM
  existant, pas un réentraînement : le modèle n'a jamais vu de feature news.
- **Le sentiment et l'impact de marché sont des estimations probabilistes.
  Ils ne garantissent en rien les mouvements futurs du marché** — l'interface
  le rappelle explicitement partout où ces scores sont affichés.

---

## Design system

- Palette sombre, deux variantes (Bleu nuit / Graphite), typographie Inter.
- Échelles cohérentes : espacements 4 px, rayons 6→18 px, quatre niveaux d'ombre.
- Densité d'affichage réglable (compacte / confortable / spacieuse).
- Contrastes vérifiés (texte 17,9:1 ; libellés 5,7:1 ; variations 5,3–8,4:1).
- Icônes Material Symbols uniquement, `aria-hidden` sur les icônes décoratives.
- Responsive vérifié à 1280 / 768 / 375 px : aucun défilement horizontal de page,
  les tableaux larges défilent dans leur propre conteneur.
- `prefers-reduced-motion` et `prefers-contrast` respectés.

---

## Dépendances

Le cœur applicatif (Streamlit, FastAPI, TensorFlow/LSTM, Plotly) est
inchangé. Dépendances ajoutées :

- `python-dotenv` — chargement de `.env`
- `transformers` — FinBERT (poids TensorFlow, pas de `torch`)
- `pytest` — suite de tests
- `sqlalchemy` — ORM / accès base de données (authentification, portefeuille)
- `bcrypt` — hachage des mots de passe
- `pyjwt` — émission/vérification des tokens de session

## Tests

```bash
pytest tests/
```

La suite couvre le preprocessing des actualités, le sentiment (repli
lexical, sans dépendre du téléchargement de FinBERT), le market impact, la
pondération de récence, l'agrégation, le client NewsAPI (entièrement mocké),
la couche de contexte de forecast (vérifie notamment que le forecast existant
reste inchangé et qu'une actualité neutre ne déplace pas la prévision), ainsi
que l'authentification, les autorisations par rôle et l'isolation des données
entre utilisateurs (`tests/test_auth.py`, `tests/test_authorization.py`,
`tests/test_data_isolation.py` — voir
[Authentification & autorisation](#authentification--autorisation)). Chaque
test tourne contre une base SQLite jetable, jamais contre `optiport.db`.
