# Optiport

Plateforme de simulation de trading ETF (paper trading) : prévision de
rendement par LSTM (un modèle par ticker), optimisation moyenne-variance,
actualités notées par sentiment/impact de marché, et un assistant IA outillé
sur les données réelles du compte — le tout servi par une API FastAPI et
consommé par une interface React.

---

## Architecture

```
React (Vite + TypeScript, port 5173)
        │  fetch, JWT en en-tête Authorization
        ▼
FastAPI (api.py, port 8000)
        │
        ├── backend/forecaster.py     LSTM par ticker, covariance, rendements attendus
        ├── backend/optimizer.py      Optimisation SLSQP, frontière efficiente
        ├── backend/news_*.py         NewsAPI → sentiment → impact → agrégation
        ├── backend/forecast_context.py  Base Forecast vs. News-Context Forecast
        ├── backend/assistant_tools.py + routers/assistant.py  Assistant IA (Groq)
        ├── backend/crud.py, models.py, db.py  SQLAlchemy / SQLite
        └── backend/security.py, deps.py       JWT, bcrypt, autorisations
        ▼
SQLite (optiport.db)
```

Aucune logique métier (calcul, authentification, exécution d'ordre) ne vit
côté frontend : React n'appelle que les endpoints FastAPI ci-dessous et
affiche leur réponse.

---

## Démarrage

Deux processus, à lancer dans deux terminaux séparés depuis la racine du
dépôt.

**1. Backend (FastAPI)**

```bash
python -m venv venv
venv\Scripts\activate          # Windows — sous macOS/Linux : source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn api:app --reload --port 8000
```

L'API est disponible sur <http://localhost:8000> ; documentation interactive
sur <http://localhost:8000/docs> (Swagger UI) et <http://localhost:8000/redoc>.

**2. Frontend (React)**

```bash
cd frontend
npm install
npm run dev
```

L'interface est disponible sur <http://localhost:5173>. Le backend doit être
démarré en premier : l'écran de connexion affiche un message d'erreur
explicite si l'API est injoignable.

Autres commandes frontend utiles : `npm run build` (vérifie les types via
`tsc -b` puis produit le build de production dans `frontend/dist/`),
`npm run preview` (sert ce build localement), `npm run lint`.

### Premier démarrage — créer le compte administrateur

Aucun mot de passe n'est codé en dur : le premier compte administrateur se
crée via une commande dédiée, qui lit les identifiants dans l'environnement
ou les demande de façon interactive (mot de passe masqué, jamais journalisé) :

```bash
python -m backend.create_admin
```

Sans variables d'environnement, la commande demande le nom d'utilisateur,
l'e-mail et le mot de passe de façon interactive (saisie masquée via
`getpass`). Avec les variables `ADMIN_*` définies (voir plus bas), elle
s'exécute sans interaction. Elle refuse d'écraser un compte existant : pour
promouvoir un compte déjà créé via l'interface, passez par
`PATCH /admin/users/{id}` une fois un premier admin en place.

---

## Structure du projet

```
api.py                        Point d'entrée FastAPI — définit /forecast,
                               /optimize, /smart-invest, /chart-data,
                               /efficient-frontier, /news/*, enregistre les
                               routers ci-dessous
backend/
├── forecaster.py             Fetch Yahoo Finance, features techniques, LSTM
│                             par ticker, rendements attendus, covariance
├── optimizer.py              Optimisation SLSQP (max Sharpe, min vol, risk
│                             parity, equal weight), frontière efficiente
├── forecast_context.py       Base Forecast (LSTM) vs. News-Context Forecast
├── news_service.py           Client NewsAPI
├── news_preprocessing.py     Nettoyage HTML/entités, déduplication
├── sentiment.py              FinBERT (repli lexical si indisponible)
├── market_impact.py          Direction/niveau/confiance d'impact de marché
├── news_recency.py           Pondération par ancienneté (décroissance expo.)
├── news_aggregator.py        Agrégation quotidienne par ticker
├── news_features.py          Traduction en features numériques pour le LSTM
├── news_analytics.py         Statistiques News Impact Analytics (KPI, tendance,
│                             corrélation actualités/prix, jamais un 2e scoring)
├── news_cache.py             Cache TTL en mémoire (prix, actualités, analytics)
├── model_evaluation.py       Métriques hors-échantillon (MAE/RMSE/MAPE/direction)
│                             sur split chronologique 70/15/15, par ticker
├── model_comparison.py       LSTM vs. Naïf/moyenne mobile/régression linéaire,
│                             même split/cible/métriques que model_evaluation.py
├── backtester.py             Simulation walk-forward sans look-ahead, rebalancée
│                             tous les 22 jours, inférence LSTM batchée par ticker
├── backtest_jobs.py          Registre de jobs en mémoire (thread d'arrière-plan)
│                             pour exposer une progression réelle au frontend
├── market_regime.py          Classification tendance/volatilité à seuils fixes
│                             sur l'historique réel de prix (jamais une prédiction)
├── risk.py                   Volatilité, Sharpe, VaR/CVaR historique, bêta,
│                             concentration, corrélations du portefeuille réel
├── performance_metrics.py    Statistiques de courbe d'equity partagées
│                             (backtester, risk) — un seul calcul, pas deux
├── portfolio_history.py      Reconstruction de la courbe d'equity depuis le
│                             grand livre réel des transactions
├── performance_attribution.py Contribution par position au rendement total —
│                             flux de cash net + valeur de marché, se recoupe
│                             exactement avec le rendement total du portefeuille
├── assistant_tools.py        Outils réels exposés à l'assistant IA (portefeuille,
│                             cotations, actualités, prévision, risque, optimisation)
├── stripe_service.py         Wrapper Stripe (Checkout, Customer Portal, vérification
│                             webhook) — ne touche jamais la base directement
├── demo_payments.py          Validation du "paiement" simulé (mode démo) — carte
│                             démo 4242 uniquement, jamais journalisée ni stockée
├── db.py, models.py, crud.py SQLAlchemy — schéma, session, opérations
├── security.py, deps.py      Hachage bcrypt, JWT, dépendances FastAPI
├── config.py                 Lecture de toutes les variables d'environnement
├── pricing.py                Cours d'exécution des ordres, faisant foi côté serveur
├── etf_metadata.py           Univers des 12 ETF (nom, région) — partagé
├── create_admin.py           CLI : python -m backend.create_admin
└── routers/
    ├── auth.py                /auth/register, /login, /logout, /me, /google*
    ├── admin.py                /admin/users, /admin/stats
    ├── portfolio.py            /portfolio/* — compte, positions, ordres,
    │                           transactions, watchlist, alertes
    ├── analytics.py            /analytics/* — model-evaluation, backtest
    │                           (sync + job/progress), market-regime, scenario
    ├── risk.py                 /risk/portfolio
    ├── billing.py              /billing/status, /checkout, /portal, /webhook,
    │                           /demo-checkout — voir Facturation & abonnements
    └── assistant.py            /assistant/status, /assistant/chat
frontend/
└── src/
    ├── pages/                 Dashboard, Markets (chart/heatmap/screener),
    │                           Portfolio, Watchlist (+ alertes), Trading, Orders,
    │                           Transactions, News, News Analytics, Analytics
    │                           (Optimizer/Smart Invest/Model Evaluation/Market
    │                           Regime/Backtesting), RiskCenter, ScenarioAnalysis,
    │                           EtfResearch, PortfolioReport, AiAssistant,
    │                           Profile, Settings, Admin, Login, Register,
    │                           GoogleCallback, Landing, Pricing, Billing,
    │                           BillingSuccess, BillingCancel, DemoCheckout
    ├── lib/                    Clients HTTP typés par domaine (authApi,
    │                           portfolioApi, marketApi, newsApi,
    │                           newsAnalyticsApi, analyticsApi, riskApi,
    │                           scenarioApi, forecastApi, assistantApi, adminApi,
    │                           billingApi), hooks React Query (queries.ts)
    ├── components/             AppShell (sidebar/topbar), Button, ThemeToggle,
    │                           StatTile, CandlestickChart, QueryState, Badge,
    │                           FilterGroup, NewsFeed ; components/auth/
    │                           (AuthLayout — panneau de marché en direct partagé
    │                           par Login/Register, PasswordInput,
    │                           GoogleContinueButton, LiveMarketPreview) ;
    │                           components/analytics/, components/newsAnalytics/
    │                           (charts par domaine, densité adaptative)
    ├── auth/                   AuthContext (session, token, restauration)
    └── theme/                  ThemeContext (clair/sombre, persisté, préférence
                                système par défaut, appliqué à toute l'app y
                                compris les pages d'authentification)
train_model.py                 Entraîne les 12 modèles LSTM (voir plus bas)
trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs/
                                Artefacts entraînés — gitignorés (voir plus bas)
tests/                          Suite pytest (voir "Tests")
```

### Principes

- **Le calcul et les mutations de compte restent au backend.** React
  n'implémente ni prévision, ni optimisation, ni exécution d'ordre, ni
  analyse de sentiment : il appelle `/forecast`, `/smart-invest`,
  `/efficient-frontier`, `/news/*`, `/assistant/chat` et `/portfolio/*`.
- **Une seule source de vérité par donnée.** Les cotations, prévisions et
  actualités sont mises en cache côté backend (TTL en mémoire) puis servies
  identiquement à toutes les pages qui en ont besoin.
- **Le backend est requis dès l'écran de connexion.** Il n'y a pas de mode
  "session anonyme" : l'inscription, la connexion et l'intégralité du
  portefeuille simulé vivent en base de données côté backend.

---

## Fonctionnalités

| Domaine | Détail |
| --- | --- |
| **Authentification** | JWT (HS256, `AUTH_SECRET_KEY`), mots de passe hachés `bcrypt`, révocation réelle au logout (table `token_blocklist`), rôle/statut actif relus en base à chaque requête (jamais depuis le token) |
| **Paper trading** | Comptes simulés dotés de 250 000 $, ordres marché/limite, prix d'exécution récupéré côté serveur (jamais fourni par le client), positions/ordres/transactions/watchlist/alertes persistés par utilisateur (SQLite, isolation stricte par `user_id`/`account_id`) |
| **Marché** | Cours, historiques OHLC, chandeliers — données réelles via `yfinance` (Yahoo Finance) |
| **Prévision LSTM** | Un modèle par ticker (12 ETF, voir plus bas) prédisant le rendement à 22 séances à partir de 9 features techniques (momentum, volatilité, drawdown, RSI, corrélation, position 52 semaines, région) |
| **Optimisation (MPT)** | `POST /optimize` — max Sharpe, min volatilité, risk parity, equal weight ; `POST /efficient-frontier` pour la frontière complète |
| **Smart Invest** | `POST /smart-invest` — combine en un seul appel la prévision LSTM (rendements attendus) et l'optimisation de portefeuille |
| **Analytics** | Frontière efficiente, allocations, répartition géographique, comparaison prévision/réalisé, exposées sur la page React "Analytics" |
| **News & Sentiment** | Pipeline complet : NewsAPI → nettoyage/déduplication → sentiment (FinBERT, repli lexical automatique) → impact de marché (direction/niveau/confiance) → pondération par ancienneté (demi-vie 6h) → agrégation quotidienne |
| **Forecast + News Context** | `POST /forecast/context` — Base Forecast (LSTM seul, inchangé) vs. News-Context Forecast (ajustement borné ±2 pt, proportionnel à sentiment × impact × confiance) |
| **News Impact Analytics** | Page "News" dédiée : KPI d'ensemble, distribution/tendance de sentiment, volume d'articles, décomposition du score d'impact, classement des actualités les plus impactantes, relation actualités/prix (corrélation, jamais causale), historique d'impact — chaque section affiche explicitement "insufficient data" plutôt que d'inventer un résultat |
| **Model Evaluation** | Métriques hors-échantillon (MAE/RMSE/MAPE/précision directionnelle) par ticker sur un split chronologique 70/15/15, courbes actual-vs-predicted, périodes train/validation/test |
| **Model Comparison Lab** | `GET /analytics/model-comparison/{ticker}` (`backend/model_comparison.py`) — compare le LSTM à trois références transparentes (Naïf/dernière valeur, moyenne mobile, régression linéaire) sur *exactement* le même split chronologique, la même cible (`return_22d`) et le même horizon que Model Evaluation (réutilise ses fonctions `_split_bounds`/`_regression_metrics` — pas une seconde méthodologie). Aucun vainqueur global n'est déclaré : chaque indicateur clé nomme la métrique sur laquelle il porte ("MAE la plus basse : X"). Limite connue : le résultat dépend entièrement de Yahoo Finance ; un échec de récupération réel n'est jamais mis en cache comme un résultat définitif (voir le commentaire dans le module). |
| **Market Regime** | `GET /analytics/market-regime` — classification tendance/volatilité transparente (seuils fixes et documentés) sur l'historique réel de prix (`backend/market_regime.py`) ; jamais une prédiction du régime futur |
| **Backtesting** | `POST /analytics/backtest` (synchrone) et `POST /analytics/backtest/start` + `GET /analytics/backtest/status/{id}` (asynchrone, avec progression réelle) — simulation walk-forward sans look-ahead, rebalancée tous les 22 jours de bourse, inférence LSTM batchée par ticker pour la performance |
| **Risk Center / Scenario Analysis** | Volatilité, Sharpe, VaR/CVaR historique, bêta, concentration (HHI), corrélations sur les positions réelles ; scénarios de stress hypothétiques (jamais appliqués au portefeuille réel) |
| **Performance Attribution** | `GET /portfolio/attribution` (`backend/performance_attribution.py`), page "Portfolio" — contribution réelle de chaque position (ouverte ou déjà clôturée) au rendement total, calculée à partir du même grand livre de transactions que tout le reste de l'app (pas une seconde comptabilité) : `contribution(ticker) = flux de cash net des BUY/SELL de ce ticker + valeur de marché actuelle`. La somme des contributions égale exactement le rendement total du portefeuille (garantie vérifiée par les tests). Limite assumée et documentée dans l'UI : seule l'attribution "depuis la création du compte" est supportée — une fenêtre glissante (ex. "30 derniers jours") demanderait une valorisation de position à une date passée que le modèle de données actuel ne conserve pas. État honnête "Insufficient portfolio history" tant qu'aucun achat/vente n'a eu lieu. |
| **ETF Screener & Heatmap** | Page "Markets" — vue tableau (prix, variation, rendement, volatilité, Sharpe, prévision, impact actualités) et vue heatmap colorée par variation réelle du jour, sur tout l'univers ETF suivi |
| **Alertes de prix** | Créées depuis la page "Watchlist", évaluées automatiquement contre les cours en direct (`backend/crud.py::settle`, appelé toutes les 60s côté client) — pas de notification push/email |
| **Assistant IA** | `Groq` (gratuit, hébergé, tool-calling) par défaut — répond en s'appuyant sur des outils réels : portefeuille de l'utilisateur, cotations, actualités notées, prévisions LSTM, **risque de portefeuille**, optimisation de portefeuille. Réponses rendues en Markdown propre côté frontend (`react-markdown` + tableaux GFM) — jamais de `**`/`\|` bruts. `OpenAI` reste disponible en alternative (`AI_PROVIDER=openai`). Aucune clé n'atteint jamais le frontend. |
| **Facturation & abonnements** | Pages "Pricing" (publique) et "Billing" (compte). Deux plans payants (Pro/Premium) au-dessus du plan Free, via **Stripe Checkout** réel (abonnement récurrent, méthodes de paiement décidées par Stripe, jamais un formulaire de carte maison) + **Customer Portal** Stripe pour gérer/annuler. Le webhook Stripe (`POST /billing/webhook`, signature vérifiée) est la seule source de vérité qui active/désactive un plan — jamais le frontend. Voir [Facturation & abonnements](#facturation--abonnements-stripe--mode-démo) pour le détail et le **mode démo** (`PAYMENT_MODE=demo`) utilisable sans compte Stripe. |

### Ce qui est réel, ce qui est simulé

| Élément | Nature |
| --- | --- |
| Cours, historiques, volumes, actualités | **Réels** — Yahoo Finance (`yfinance`) et NewsAPI |
| Prévisions LSTM, poids optimisés, frontière efficiente | **Réels** — 12 modèles entraînés, calculés par le backend |
| Sentiment, impact de marché | **Réels, mais probabilistes** — ne garantissent aucun mouvement futur |
| Comptes, positions, ordres, transactions, watchlist, alertes | **Persistés** en base (SQLite), propres à chaque utilisateur — mais l'exécution des ordres reste **simulée** (paper trading, aucun ordre transmis à un courtier) |
| Prix d'exécution des ordres | **Réels** au moment du remplissage — récupérés par le backend, jamais fournis par le client |

### Parcours de démonstration (PFE)

Un enchaînement qui couvre l'ensemble de l'application réelle, du plus général au plus spécifique :

1. **Landing** (`/`) — bandeau de cours en direct, présentation du produit
2. **Inscription / Connexion** — compte simulé doté de 250 000 $
3. **Dashboard** — vue d'ensemble du compte, performance réelle (état honnête si l'historique est insuffisant)
4. **Markets** — recherche, graphique, **Heatmap**, **Screener**
5. **News** — actualités + Quantitative News Impact Analytics
6. **Analytics → Model Evaluation** — précision hors-échantillon des 12 modèles LSTM
7. **Analytics → Market Regime** — classification tendance/volatilité
8. **Analytics → Portfolio Optimizer** — allocation optimisée + frontière efficiente
9. **Analytics → Smart Invest** — recommandation guidée → exécution en paper trading
10. **Risk Center** — volatilité, Sharpe, VaR/CVaR, corrélations du portefeuille réel
11. **Scenario Analysis** — stress-tests hypothétiques (jamais appliqués au compte réel)
12. **Analytics → Backtesting** — simulation walk-forward, progression réelle, courbe d'equity + drawdown
13. **Trading / Orders / Transactions** — passage d'ordres réels (simulés), historique
14. **Watchlist** — suivi de tickers + alertes de prix
15. **Report** — rapport de portefeuille consolidé
16. **AI Assistant** — questions en langage naturel, réponses formatées, toujours issues des mêmes données réelles
17. **Pricing → Billing** — mise à niveau Pro/Premium (Stripe réel ou mode démo selon `PAYMENT_MODE`), page Billing reflétant le plan actif
18. **Admin** *(compte administrateur uniquement)*

---

## Modèles LSTM

### Univers (12 ETF)

`PSI`, `IYW`, `RING`, `PICK`, `NLR`, `UTES`, `LIT`, `NANR`, `GUNR`, `XCEM`,
`PTLC`, `FXU` (noms et régions dans `backend/etf_metadata.py`).

### Architecture et features

Un modèle **par ticker** : `LSTM(16) → Dropout(0.2) → Dense(1)`, séquences de
10 pas de temps, 9 features par pas (`corr_3m`, `max_dd_6m`, `momentum_1m`,
`momentum_3m`, `momentum_6m`, `vol_1m`, `Region_Encoded`, `rsi_14`,
`position_52w` — voir `backend/forecaster.py::FEATURE_COLS`), mise à
l'échelle par `RobustScaler` (un par ticker). Cible : rendement à 22 séances.

### Artefacts entraînés — gitignorés, à régénérer localement

Les fichiers `.keras` et `scalers.pkl` sont volumineux, binaires, et
**volontairement exclus du dépôt** (`.gitignore` : `trained_models_LSTM_2000_epochs/`,
`*.keras`, `*.pkl`). **Un clone frais du dépôt n'a donc aucun modèle entraîné**
tant que l'entraînement n'a pas été relancé localement.

Pour les régénérer :

```bash
python train_model.py                    # entraîne les 12 tickers
python train_model.py --tickers PSI IYW  # ou un sous-ensemble
```

Le script télécharge l'historique complet (Yahoo Finance, depuis 2010),
recalcule les features exactement comme `backend/forecaster.py` (aucune
divergence train/inférence possible : le script importe directement les
fonctions du module d'inférence), entraîne chaque modèle avec arrêt anticipé,
puis sauvegarde :

```
trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs/
├── PSI_model.keras
├── IYW_model.keras
├── ... (un par ticker)
└── scalers.pkl              (dict {ticker: RobustScaler}, fusionné —
                               un entraînement partiel ne détruit pas les
                               scalers déjà sauvegardés pour les autres tickers)
```

Comptez quelques minutes par ticker sur CPU (pas de GPU requis — chaque
modèle ne fait que 1 681 paramètres). **Prérequis Windows** : TensorFlow
nécessite le Microsoft Visual C++ Redistributable 2015–2022 (x64) —
`winget install --id Microsoft.VCRedist.2015+.x64 -e` s'il manque
(`ImportError: ... msvcp140.dll`).

**En l'absence de modèles**, le backend ne renvoie pas d'erreur : `/forecast`
retombe sur le dernier rendement observé à 22 séances (`model_loaded:
false`, champ `note` explicite par ticker). Un message est aussi affiché au
démarrage du serveur (`[optiport] LSTM models found: N (...)` ou l'avertissement
correspondant) pour vérifier rapidement l'état sans appeler l'API.

Le chemin des modèles est résolu par rapport à la racine du projet
(`backend/forecaster.py::resolve_model_dir`), pas au répertoire de travail du
processus — démarrer le serveur depuis un autre dossier ne casse donc pas la
détection des modèles. Sur un hébergeur qui reconstruit le code depuis Git à
chaque déploiement (ce chemin relatif serait alors vidé à chaque fois),
définir `LSTM_MODEL_DIR` sur un chemin absolu vers un disque
persistant/volume monté prend le dessus sur ce défaut — voir
[DEPLOYMENT.md](DEPLOYMENT.md).

Un corollaire pratique : si un seul fichier `.keras` est corrompu ou
incompatible, seul ce ticker retombe en mode dégradé — les autres tickers de
la même requête `/forecast` restent prédits normalement.

---

## Authentification & autorisation

- **Mots de passe** : hachés avec `bcrypt` (jamais stockés ni journalisés en
  clair). Aucune route ne renvoie `password_hash`.
- **Sessions** : tokens JWT (HS256), signés avec `AUTH_SECRET_KEY`. Le rôle et
  le statut actif/désactivé ne sont **jamais** lus depuis le token :
  `backend/deps.py` les relit en base à chaque requête — désactiver un compte
  ou changer son rôle prend effet immédiatement, même sur un token non expiré.
- **Déconnexion réelle** : `POST /auth/logout` place le `jti` du token dans
  `token_blocklist` — révocation côté serveur, pas seulement côté client.
- **Toutes les routes exigent un token valide**, sauf `/auth/register`,
  `/auth/login` et `/health`. Les routes `/admin/*` exigent en plus le rôle
  `admin`, revérifié à chaque appel.
- **Isolation des données** : chaque requête sur `/portfolio/*` est filtrée
  par l'utilisateur appelant ; une ressource appartenant à un autre
  utilisateur renvoie `404`, pas `403`.
- **Prix d'exécution faisant foi côté serveur** : un ordre au marché n'est
  jamais rempli au prix envoyé par le client.
- **Deux méthodes de connexion** : nom d'utilisateur + mot de passe, ou
  "Continue with Google" — les deux émettent le même JWT Optiport et
  utilisent exactement la même isolation des données ; voir
  [Connexion avec Google](#connexion-avec-google) ci-dessous.

### Schéma de base de données (SQLite, `backend/models.py`)

```
users (+ plan, stripe_customer_id, stripe_subscription_id,
        subscription_status, current_period_end)
users            1───1  accounts (cash simulé)
                          │
                          ├──* positions   (ticker, quantité, prix moyen)
                          ├──* orders      (sens, quantité, type, statut, prix d'exécution…)
                          └──* transactions
users            1───*  watchlist_items
users            1───*  alerts
                  *  token_blocklist (jti des tokens révoqués)
```

Suppression en cascade (`ondelete=CASCADE`) sur chaque table dépendante :
supprimer un utilisateur supprime proprement tout ce qui lui appartient.
`Base.metadata.create_all()` (appelé au démarrage du backend) crée le schéma
s'il n'existe pas encore et ne touche jamais aux tables existantes.

### Connexion avec Google

Flux : Login → bouton "Continue with Google" → page d'authentification
Google → Google redirige vers `GET /auth/google/callback` **côté backend**
(c'est cette URL, pas une page React, qui est enregistrée comme "Authorized
redirect URI" sur le client OAuth Google — FastAPI reçoit le code
d'autorisation directement) → le backend échange le code, crée/relie le
compte, émet le JWT Optiport habituel, puis redirige le navigateur vers
`{FRONTEND_URL}/auth/google/callback#access_token=...` (React) → la page
adopte le token (fragment d'URL, jamais transmis à un serveur, jamais dans
les logs) → `/app/dashboard`. Le token émis, la révocation au logout,
l'isolation des données : tout est **identique** à une connexion par mot de
passe — Google ne fait que fournir une identité vérifiée en amont. En cas
d'échec (refus Google, code invalide, compte désactivé), le backend
redirige vers la même page React avec `?error=...` au lieu du fragment —
jamais une erreur JSON brute affichée au milieu d'une redirection Google.

**Vérifications côté serveur** (`backend/google_oauth.py`), jamais côté
client :
- Échange du code d'autorisation contre un jeton Google — le secret client
  (`GOOGLE_CLIENT_SECRET`) ne quitte jamais ce module, jamais transmis au
  frontend.
- Le jeton d'identité Google est vérifié via `google-auth`
  (`google.oauth2.id_token.verify_oauth2_token`), pas décodé sans
  validation : signature RS256 contre les clés publiques Google actuelles,
  émetteur (`iss`) restreint à Google, audience (`aud`) comparée à notre
  propre `GOOGLE_CLIENT_ID` (jamais une valeur fournie par le client),
  expiration (`exp`) vérifiée. Les claims `sub`/`email` sont requis avant de
  faire confiance à l'identité.
- **Protection contre la prise de contrôle de compte** : une identité
  Google n'est associée à un compte Optiport *existant* que si Google
  rapporte l'e-mail comme vérifié (`email_verified`) — sinon `409 Conflict`
  plutôt qu'une association silencieuse. Le rapprochement se fait d'abord
  par `google_sub` (identifiant stable et non-devinable propre à Google),
  jamais par e-mail seul.
- Un compte créé via Google reçoit un hash de mot de passe aléatoire,
  jamais partagé (voir le commentaire sur `User.password_hash`) — impossible
  de s'y connecter par mot de passe, seulement via Google.
- Compte désactivé, rôle, isolation des données : tous les contrôles
  existants s'appliquent identiquement, quelle que soit la méthode de
  connexion.

**Configuration** (`.env`, voir `.env.example`) : `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` — les trois requis ensemble ou
le bouton reste caché sur la page Login (`GET /auth/google/config` est
interrogé par React et ne renvoie `enabled: true` que si les trois sont
définis — jamais de bouton qui simule une connexion impossible).
`FRONTEND_URL` (optionnel, défaut `http://localhost:5173`) indique au
backend où rediriger le navigateur une fois l'échange terminé.

**Endpoints** : `GET /auth/google/config` (public, jamais le secret client),
`GET /auth/google/callback` (où Google redirige réellement — jamais appelé
directement par le frontend), `POST /auth/google` (échange direct
code→JWT pour un client non-navigateur qui gérerait lui-même le code — le
frontend React actuel utilise `GET /auth/google/callback`, pas cette route).

---

## Facturation & abonnements (Stripe + mode démo)

Trois plans : **Free** (inclus par défaut), **Pro** (9,99 $/mois), **Premium**
(19,99 $/mois) — présentés sur la page publique `/pricing`, gérés depuis
`/app/billing` une fois connecté. `User.plan` / `subscription_status` /
`current_period_end` (`backend/models.py`) sont le seul état de plan lu par le
reste de l'app ; **rien d'autre que le webhook Stripe (ou son équivalent en
mode démo) n'écrit ces colonnes** — ni `POST /billing/checkout`, ni le
frontend, ne marquent jamais un utilisateur comme mis à niveau eux-mêmes.

### Deux modes, un seul état de plan

`PAYMENT_MODE` (`.env`) choisit le flux de paiement réel utilisé par
`/pricing` :

| Mode | Quand | Flux |
| --- | --- | --- |
| `stripe` | Un compte Stripe (test ou live) est configuré | Checkout Session Stripe hébergée → webhook Stripe (`POST /billing/webhook`, signature vérifiée) → `plan`/`subscription_status`/`current_period_end` synchronisés depuis l'abonnement Stripe réel |
| `demo` | Aucune clé Stripe définie (ex. compte Stripe indisponible pour ce projet) | Page `/checkout/demo` intégrée à l'app — carte **démo uniquement** (`4242 4242 4242 4242`, toute autre valeur est refusée), bandeau "DEMO PAYMENT — NO REAL MONEY WILL BE CHARGED" à chaque étape, activation immédiate et synchrone (pas de webhook à attendre) |

Non défini, `PAYMENT_MODE` est déduit automatiquement : `stripe` si
`STRIPE_SECRET_KEY` + les deux Price ID sont définis, `demo` sinon — la page
Pricing ne se retrouve donc jamais avec des boutons "Upgrade" qui ne peuvent
rien faire. Les deux modes appellent la **même** logique d'activation
(`backend/crud.py::apply_subscription_state` / `activate_demo_subscription`) :
aucune duplication de la logique d'abonnement entre les deux chemins.

**Sécurité du mode démo** (`backend/demo_payments.py`) : les champs de carte
saisis ne sont ni journalisés, ni stockés — validés en mémoire dans un seul
appel puis abandonnés. L'identifiant d'abonnement généré (`demo_...`) ne
ressemble jamais à un vrai `sub_...` Stripe, pour rester repérable en base.

**Stripe** (`backend/stripe_service.py`, `backend/routers/billing.py`) :
- `POST /billing/checkout` — crée/réutilise un Customer Stripe puis une
  Checkout Session en mode abonnement ; les méthodes de paiement proposées
  (carte, Apple Pay, Google Pay, Link…) sont décidées par la configuration du
  Dashboard Stripe, jamais codées en dur ici.
- `POST /billing/portal` — Customer Portal Stripe (changement de moyen de
  paiement, factures, annulation) ; aucune logique d'annulation maison.
- `POST /billing/webhook` — authentifié par la signature `Stripe-Signature`
  (pas un token JWT, Stripe est l'appelant), gère
  `checkout.session.completed`, `customer.subscription.{created,updated,deleted}`
  et `invoice.payment_failed` ; toujours répond `200` sur un événement
  reconnu-mais-ignoré pour éviter les relances Stripe, `400` uniquement sur
  signature invalide.

**Aucune donnée de carte réelle ne transite ni ne persiste jamais côté
Optiport**, dans les deux modes : Stripe Checkout est hébergé par Stripe, et
le mode démo n'accepte qu'un numéro de carte factice.

---

## Variables d'environnement (`.env`, voir `.env.example`)

Copiez `.env.example` vers `.env` à la racine du dépôt (déjà gitignoré) et
complétez selon vos besoins :

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `AUTH_SECRET_KEY` | Clé de signature des JWT | Générée aléatoirement au démarrage si absente — **tous les tokens deviennent invalides au redémarrage** ; à définir explicitement pour des sessions stables |
| `AUTH_TOKEN_EXPIRE_MINUTES` | Durée de vie d'un token | `480` (8 h) |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///<racine du repo>/optiport.db` |
| `LSTM_MODEL_DIR` | Chemin absolu vers les modèles LSTM, prioritaire sur le chemin relatif au dépôt (utile hors dev local, voir [DEPLOYMENT.md](DEPLOYMENT.md)) | — (chemin relatif au dépôt) |
| `NEWS_API_KEY` | Clé NewsAPI (module News/Sentiment) — optionnel, `/news/*` renvoie une erreur explicite si absente | — |
| `CORS_ALLOWED_ORIGINS` | Origines autorisées, séparées par des virgules | `http://localhost:5173` (serveur de dev Vite) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | "Continue with Google" sur Login — les trois requis ensemble, sinon le bouton reste caché. `GOOGLE_REDIRECT_URI` pointe vers ce backend (`GET /auth/google/callback`), pas vers React (voir [Connexion avec Google](#connexion-avec-google)) | — |
| `FRONTEND_URL` | Où `GET /auth/google/callback` redirige le navigateur une fois l'échange terminé | `http://localhost:5173` |
| `AI_PROVIDER` | `groq` (par défaut, gratuit, hébergé) ou `openai` | `groq` |
| `GROQ_API_KEY` / `GROQ_MODEL` | Utilisés si `AI_PROVIDER=groq`. Clé gratuite : console.groq.com/keys. Le modèle doit supporter le tool-calling **et être disponible sur votre compte** — vérifiez avec `client.models.list()` en cas de 404 | — / `openai/gpt-oss-120b` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Utilisés si `AI_PROVIDER=openai` | — / `gpt-4o-mini` |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_FULL_NAME` | Bootstrap du premier admin (`python -m backend.create_admin`) | Demandés de façon interactive si absents |
| `PAYMENT_MODE` | `demo` ou `stripe` — voir [Facturation & abonnements](#facturation--abonnements-stripe--mode-démo) | Déduit automatiquement (`stripe` si les variables Stripe ci-dessous sont toutes définies, `demo` sinon) |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Clé API Stripe (mode test ou live) et secret de vérification du webhook | — |
| `STRIPE_PRO_PRICE_ID` / `STRIPE_PREMIUM_PRICE_ID` | Price ID Stripe (récurrents) des plans Pro/Premium | — |

`NEWS_API_KEY`, `GROQ_API_KEY`/`OPENAI_API_KEY` et `AUTH_SECRET_KEY` ne sont
lus que côté backend (`backend/config.py`) : ils ne transitent jamais vers le
frontend, n'apparaissent dans aucune réponse d'API ni aucun log.

---

## Tests

```bash
pytest tests/
```

Ces tests couvrent : authentification, autorisations par rôle et isolation
des données entre utilisateurs (`test_auth.py`, `test_authorization.py`,
`test_data_isolation.py`), marché — cotations et OHLC, mise en cache (`test_market_quotes.py`,
`test_market_ohlc.py`), pipeline actualités — preprocessing, sentiment,
market impact, pondération de récence, agrégation, client NewsAPI mocké
(`test_news_*.py`, `test_market_impact.py`, `test_sentiment.py`), contexte de
prévision — vérifie que le Base Forecast reste inchangé et qu'une actualité
neutre ne déplace pas la prévision (`test_forecast_context.py`),
performance/cache (`test_performance.py`, `test_ttl_cache.py`),
facturation — Stripe mocké à la frontière `stripe_service`, webhook (signature,
activation/annulation/échec de paiement), et mode démo (carte démo uniquement,
persistance du plan à travers logout/login) (`test_billing.py`,
`test_demo_payments.py`), ainsi que model evaluation/comparison, backtesting,
market regime, risk, scenario analysis et performance attribution
(`test_model_evaluation.py`, `test_model_comparison.py`, `test_backtester.py`,
`test_market_regime.py`, `test_risk*.py`, `test_scenario_router.py`,
`test_performance_attribution.py`).

Chaque test tourne contre une base SQLite jetable (fichier temporaire),
jamais contre `optiport.db` — voir `tests/conftest.py`.

Vérification des types frontend :

```bash
cd frontend
npx tsc -b
```

---

## Documentation API

Une fois le backend démarré : Swagger UI interactif sur
<http://localhost:8000/docs>, schéma OpenAPI brut sur
<http://localhost:8000/openapi.json>, ReDoc sur
<http://localhost:8000/redoc>.

---

## Déploiement en production

Ce projet démarre en développement avec `uvicorn --reload` (backend) et
`vite dev` (frontend), tous deux liés à `localhost`. Pour un déploiement réel,
essentiellement des changements de **configuration** — le seul changement de
code fait pour permettre ceci est `LSTM_MODEL_DIR` (voir
[Modèles LSTM](#modèles-lstm)), pour que les modèles entraînés puissent
vivre hors du dépôt sur un hébergeur qui reconstruit le code à chaque
déploiement.

> Pour l'architecture concrète **Vercel (frontend) + Render (backend)**,
> voir [DEPLOYMENT.md](DEPLOYMENT.md) — checklist complète, variables
> d'environnement exactes, et stratégie retenue pour fournir les modèles
> LSTM sans les committer.

Général (indépendant de l'hébergeur choisi) :

### Backend

- **`AUTH_SECRET_KEY`** : à définir explicitement (`python -c "import
  secrets; print(secrets.token_hex(32))"`). Sans elle, une clé aléatoire est
  générée à chaque démarrage — tous les tokens deviennent invalides au
  redémarrage suivant, inacceptable en production.
- **`CORS_ALLOWED_ORIGINS`** : à définir avec l'origine réelle du frontend
  déployé (ex. `https://app.mondomaine.com`). Sans elle, seul le serveur de
  dev Vite (`localhost:5173`) est autorisé — le frontend déployé ne pourra
  pas appeler l'API.
- **Liaison réseau** : `uvicorn api:app --host 0.0.0.0 --port 8000` (sans
  `--reload`, qui recharge le code à chaque changement de fichier — coûteux
  et inutile en production). `--host 0.0.0.0` est nécessaire dès que le
  processus tourne dans un conteneur/VM séparé du reverse proxy — le défaut
  d'Uvicorn (`127.0.0.1`) n'est joignable que depuis la même machine.
- **Plusieurs workers** : `uvicorn api:app --host 0.0.0.0 --port 8000
  --workers 4` (ou un gestionnaire de process dédié — Gunicorn avec des
  workers Uvicorn, systemd, un orchestrateur de conteneurs) pour utiliser
  plusieurs cœurs CPU sous charge concurrente.
- **Reverse proxy / TLS** : ce backend ne termine pas TLS lui-même — le
  placer derrière Nginx/Caddy/un load balancer gérant HTTPS, comme pour
  n'importe quelle API FastAPI.

### Frontend

- Définir `VITE_API_BASE_URL` (voir `frontend/.env.example`) sur l'URL
  publique réelle du backend **avant** `npm run build` — Vite l'intègre au
  moment du build, pas à l'exécution.
- `npm run build` produit un site statique dans `frontend/dist/` : à servir
  tel quel par n'importe quel hébergeur statique/CDN/reverse proxy (aucun
  serveur Node requis en production).

### Base de données (SQLite)

SQLite reste adapté à ce projet — un seul processus backend, un volume de
données correspondant à une démo/un usage interne, pas de besoin de scaling
horizontal identifié. Deux points déjà couverts par `backend/db.py` :
`PRAGMA foreign_keys=ON` (cascade de suppression) et, désormais, `PRAGMA
journal_mode=WAL` + `synchronous=NORMAL` — le mode WAL permet aux lectures de
continuer pendant qu'une écriture est en cours (au lieu de verrouiller tout
le fichier), ce qui compte dès que plusieurs utilisateurs sont actifs en même
temps. Migrer vers PostgreSQL n'est pas nécessaire tant qu'un besoin concret
de scaling horizontal ou d'accès concurrent depuis plusieurs processus
backend ne se présente pas.

### Artefacts LSTM (`.keras`, `scalers.pkl`)

Volontairement exclus du dépôt (voir [Modèles LSTM](#modèles-lstm)) — donc
absents de toute image/déploiement construit à partir d'un `git clone` brut.
Trois stratégies pratiques, par ordre de préférence croissante avec la
taille de l'équipe/l'infrastructure :

1. **Étape de build** : exécuter `python train_model.py` une fois pendant la
   construction de l'image de déploiement (Dockerfile `RUN`, étape CI), pour
   qu'il fasse partie de l'image finale sans jamais transiter par git.
2. **Stockage objet externe** : uploader `trained_models_LSTM_2000_epochs/`
   une fois vers S3/GCS/équivalent après un entraînement local, puis le
   télécharger au démarrage du conteneur (avant `uvicorn`) via un script
   d'entrée (`entrypoint.sh`).
3. **Volume persistant monté manuellement** : pour un déploiement à un seul
   serveur (VM), copier le dossier une fois via `scp`/`rsync` sur le volume
   du serveur — le chemin étant résolu par rapport à la racine du projet
   (`backend/forecaster.py::resolve_model_dir`), peu importe le répertoire de
   travail du processus au démarrage.

Dans les trois cas, **aucun changement de code n'est nécessaire** : le
backend démarre normalement sans modèles (repli sur le dernier rendement
observé, voir [Modèles LSTM](#modèles-lstm)) et les détecte automatiquement
dès qu'ils apparaissent au chemin attendu, au prochain redémarrage.

### Résilience aux pannes de services externes

Déjà couvert par le code existant, vérifié pendant cet audit — aucune panne
externe ne fait planter le processus backend, chacune dégrade proprement
vers un état explicite :

| Service externe | Comportement en cas de panne |
| --- | --- |
| Yahoo Finance (`yfinance`) | `backend/pricing.py` capture toute exception et renvoie un dict/liste vide plutôt que de propager — le endpoint répond avec les tickers manquants signalés, pas une erreur 500 générique |
| NewsAPI | `NewsServiceError` typée (`no_api_key`, `invalid_key`, `rate_limit`, `timeout`, `unavailable`) mappée à un code HTTP précis ; `/news/*` renvoie un message explicite, jamais un crash |
| Groq / OpenAI (Assistant IA) | `/assistant/status` renvoie `available: false` avec une raison lisible (clé absente, quota épuisé, timeout réseau…) ; le frontend affiche cet état au lieu de proposer un chat cassé |
| Modèles LSTM | Absents, manquants pour un ticker, ou fichier corrompu : chaque cas dégrade **par ticker** (voir [Modèles LSTM](#modèles-lstm)) — un seul fichier cassé n'affecte jamais les autres tickers de la même requête `/forecast` |

---

## Migration React — état

L'interface Streamlit d'origine a été entièrement retirée (plus de `app.py`,
`views/`, `ui/`, `services/`, dépendances `streamlit`/`plotly`/`altair`) :
React + Vite est désormais la seule interface. Le backend FastAPI et le
schéma de base de données n'ont pas changé dans cette transition — seule la
couche de présentation a été remplacée.
