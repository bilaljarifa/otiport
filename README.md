# Optiport

Plateforme d'allocation d'ETF : prévision de rendement par LSTM (un modèle par
ticker) et optimisation moyenne-variance, exposées dans une interface de type
terminal de marché.

---

## Démarrage

Deux processus sont nécessaires : le backend FastAPI (modèle + optimiseur) et
l'interface Streamlit.

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

### Dans VS Code

Ouvrez le dossier `Optiport` (et non le dossier parent) dans VS Code, puis :

- **F5** → « ▶ Optiport (API + Interface) » lance les deux serveurs en même
  temps, avec le débogueur. Arrêter la session arrête les deux.
- Ou **Terminal → Exécuter la tâche… → « Optiport : démarrer tout »** pour les
  lancer sans débogueur.

Les fichiers `.vscode/` fournissent ces configurations et pointent
automatiquement sur l'environnement virtuel `venv/`. L'extension **Python** de
Microsoft doit être installée (elle fournit le débogueur pour le F5).

> Sans backend, l'interface reste utilisable : cotations, historiques, tableaux,
> graphiques et compte simulé fonctionnent. Seules l'optimisation, les
> prévisions et la frontière efficiente sont indisponibles, et les pages
> concernées l'indiquent explicitement.

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
│   ├── api_client.py   Client HTTP du backend, avec erreurs typées
│   ├── store.py        État de session : portefeuille simulé, ordres, alertes, préférences
│   ├── analytics.py    Mesures de risque et de performance calculées pour l'affichage
│   └── context.py      Contexte partagé, résolu une fois par exécution
├── views/              Une page = un module (exécuté à la demande)
├── api.py              API FastAPI
└── backend/            Logique métier — inchangée
    ├── forecaster.py   Features, LSTM, rendements attendus, covariance
    └── optimizer.py    Optimisation SLSQP, frontière efficiente, recommandations
```

### Principes

- **Le calcul reste au backend.** L'interface n'implémente ni prévision ni
  optimisation : elle appelle `/smart-invest`, `/forecast`, `/chart-data` et
  `/efficient-frontier`. `services/analytics.py` ne contient que des mesures
  d'affichage (volatilité, Sharpe, drawdown, corrélations, attribution).
- **Une seule source de vérité par donnée.** Les cotations sont récupérées en
  un appel par exécution, mises en cache, puis partagées via `services/context.py`.
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

---

## Ce qui est réel, ce qui est simulé

L'interface distingue systématiquement les deux :

| Élément | Nature |
| --- | --- |
| Cours, historiques, volumes, actualités | **Réels** — Yahoo Finance via `yfinance` |
| Prévisions, poids optimisés, frontière efficiente | **Réels** — calculés par le backend |
| Signaux techniques (Strong Buy → Avoid) | **Calculés** — indicateur composite documenté dans l'interface, non prédictif |
| Positions, ordres, liquidités, transactions | **Simulés** — paper trading, aucun ordre transmis |

Le compte de démonstration est doté de 250 000 $. Les ordres au marché sont
servis au dernier cours connu, les ordres à cours limité lorsque le cours
franchit le seuil (évalué à chaque chargement de page).

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

- Pas de base de données : les actualités analysées sont mises en cache en
  mémoire process (~20 min, `backend/news_cache.py`), pas persistées entre
  redémarrages du backend.
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
inchangé. Trois dépendances ajoutées pour le module News/Sentiment :

- `python-dotenv` — chargement de `.env`
- `transformers` — FinBERT (poids TensorFlow, pas de `torch`)
- `pytest` — suite de tests (`backend/`)

## Tests

```bash
pytest tests/
```

42 tests couvrent le preprocessing, le sentiment (repli lexical, sans
dépendre du téléchargement de FinBERT), le market impact, la pondération de
récence, l'agrégation, le client NewsAPI (entièrement mocké) et la couche de
contexte de forecast (vérifie notamment que le forecast existant reste
inchangé et qu'une actualité neutre ne déplace pas la prévision).
