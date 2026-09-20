# Déploiement — Vercel (frontend) + Render (backend)

Ce document couvre uniquement la préparation au déploiement pour
l'architecture cible : **React/Vite → Vercel**, **FastAPI → Render**, SQLite
+ WAL comme base de données du MVP, modèles LSTM fournis séparément (jamais
via Git), Yahoo Finance / NewsAPI / Groq comme services externes.

Rien n'a été déployé — ce document et les fichiers de configuration qui
l'accompagnent (`render.yaml`, `frontend/vercel.json`, `runtime.txt`)
préparent le déploiement sans l'exécuter.

---

## 1. Frontend — configuration Vercel

**Déjà correct, aucun changement de code nécessaire** :
`frontend/src/lib/apiClient.ts` lit `VITE_API_BASE_URL` au moment du build
(`import.meta.env.VITE_API_BASE_URL`), avec `http://localhost:8000` comme
repli pour le développement uniquement. Il suffit de définir cette variable
dans Vercel pour qu'elle pointe vers l'URL publique du backend Render.

**Ajouté** : `frontend/vercel.json` — sans lui, un lien direct vers une route
React Router (ex. `https://optiport.vercel.app/app/dashboard`, un
rafraîchissement de page, ou un lien partagé) renvoie 404, puisque Vercel sert
des fichiers statiques par défaut et qu'aucun fichier physique n'existe à ce
chemin. La règle de réécriture fait retomber toute route sur `index.html`,
laissant React Router gérer le routing côté client.

### Configuration du projet Vercel (tableau de bord)

| Paramètre | Valeur |
| --- | --- |
| **Root Directory** | `frontend` |
| **Framework Preset** | Vite (détecté automatiquement) |
| **Build Command** | `npm run build` (défaut détecté, inchangé) |
| **Output Directory** | `dist` (défaut détecté, inchangé) |
| **Install Command** | `npm install` (défaut) |

### Variable d'environnement Vercel

| Variable | Valeur | Scope |
| --- | --- | --- |
| `VITE_API_BASE_URL` | URL publique HTTPS du service Render (ex. `https://optiport-api.onrender.com`) | Production (et Preview si vous voulez que les preview deployments Vercel appellent aussi le backend réel) |

---

## 2. Backend — configuration Render

**Déjà correct** : CORS (`backend/config.py::cors_allowed_origins`) et
`AUTH_SECRET_KEY` sont déjà entièrement pilotés par variables
d'environnement (voir audit de production readiness précédent) — aucun
changement de code nécessaire pour ces deux points.

**Ajouté** : `runtime.txt` (`python-3.10.11`) — sans lui, Render utilise sa
version Python par défaut, potentiellement plus récente que ce que
TensorFlow/tf_keras supportent, ce qui ferait échouer `pip install -r
requirements.txt` de façon peu explicite. Render lit aussi `PYTHON_VERSION`
en variable d'environnement (voir `render.yaml`) — les deux mécanismes sont
inclus par sécurité.

**Ajouté** : `requirements.txt` — les versions étaient jusqu'ici non
épinglées (`fastapi` au lieu de `fastapi==0.141.1`). Sur un environnement de
build frais comme Render, cela peut résoudre des versions différentes de
celles testées localement — épinglé aux versions exactes actuellement
installées et testées (106→96 tests passants tout au long de ce projet).

**Ajouté** : `backend/config.py::lstm_model_dir()` + un import dans
`backend/forecaster.py` — voir section 4, c'est le changement qui rend le
point suivant possible sans jamais committer les modèles.

### Commande de build Render

```
pip install -r requirements.txt
```

### Commande de démarrage Render (exacte)

```
uvicorn api:app --host 0.0.0.0 --port $PORT
```

Points critiques, tous déjà couverts par cette commande :
- **`--host 0.0.0.0`** — Render route le trafic public vers le conteneur ;
  le défaut d'Uvicorn (`127.0.0.1`) ne serait joignable que depuis
  l'intérieur du conteneur lui-même.
- **`--port $PORT`** — Render assigne dynamiquement le port réel via la
  variable d'environnement `PORT` (non choisie par vous) ; coder un port en
  dur (`--port 8000`) ferait échouer le service.
- **Pas de `--reload`** — inutile et coûteux hors développement.

### Health check

Render peut sonder `/health` (déjà existant, sans authentification) pour
détecter un déploiement qui ne démarre pas correctement — configuré dans
`render.yaml` (`healthCheckPath: /health`).

---

## 3. Variables d'environnement — liste complète

### Backend (Render)

| Variable | Obligatoire | Valeur pour ce déploiement |
| --- | --- | --- |
| `AUTH_SECRET_KEY` | **Oui** | Générer avec `python -c "import secrets; print(secrets.token_hex(32))"`, saisir dans le tableau de bord Render (jamais dans `render.yaml`, jamais dans Git) |
| `CORS_ALLOWED_ORIGINS` | **Oui** | L'URL de production Vercel exacte, ex. `https://optiport.vercel.app` |
| `DATABASE_URL` | Oui (pour la persistance) | `sqlite:////var/data/optiport.db` — voir section 5 |
| `LSTM_MODEL_DIR` | Oui (pour la persistance) | `/var/data/lstm_models` — voir section 4 |
| `NEWS_API_KEY` | Oui (sinon `/news/*` renvoie une erreur explicite mais propre) | Votre clé NewsAPI |
| `AI_PROVIDER` | Non (défaut `groq`) | `groq` |
| `GROQ_API_KEY` | Oui si `AI_PROVIDER=groq` | Votre clé Groq |
| `GROQ_MODEL` | Non (défaut déjà correct) | `openai/gpt-oss-120b` — vérifier qu'il reste disponible sur votre compte |
| `AUTH_TOKEN_EXPIRE_MINUTES` | Non (défaut 480) | `480` |
| `PYTHON_VERSION` | Recommandé | `3.10.11` |
| `GOOGLE_CLIENT_ID` | Oui pour activer "Continue with Google" (sinon le bouton reste caché — pas d'erreur) | Depuis Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Idem | Depuis Google Cloud Console — jamais transmis au frontend |
| `GOOGLE_REDIRECT_URI` | Idem | `https://<votre-service>.onrender.com/auth/google/callback` — **doit pointer vers ce backend Render** (`GET /auth/google/callback` y est une vraie route FastAPI, pas une page React), et être ajoutée telle quelle comme "Authorized redirect URI" sur le client OAuth Google |
| `FRONTEND_URL` | Idem | `https://<votre-domaine-vercel>` — où le backend redirige le navigateur une fois l'échange terminé (succès ou échec) |
| `ADMIN_USERNAME`/`ADMIN_EMAIL`/`ADMIN_PASSWORD`/`ADMIN_FULL_NAME` | Non — utilisés une seule fois | Voir section 8, étape de bootstrap admin |

`OPENAI_API_KEY`/`OPENAI_MODEL` uniquement si vous prévoyez de basculer
`AI_PROVIDER=openai` plus tard — pas nécessaire pour cette architecture.

### Frontend (Vercel)

| Variable | Obligatoire | Valeur |
| --- | --- | --- |
| `VITE_API_BASE_URL` | **Oui — la seule variable frontend qui existe dans tout le projet** (vérifié : aucune autre référence à `import.meta.env` dans `frontend/src`) | URL publique du service Render |

---

## 4. Modèles LSTM (12 `.keras` + `scalers.pkl`) sans jamais les committer

**Le problème concret sur Render** : Render reconstruit le code depuis Git à
chaque déploiement — le chemin relatif au dépôt qu'utilisait déjà le projet
(`backend/forecaster.py::resolve_model_dir`, ancré sur la racine du dépôt)
pointerait donc vers un répertoire vidé à chaque redéploiement, même si vous
y aviez copié les modèles manuellement une fois.

**Solution retenue** (le changement de code minimal fait dans le cadre de
cette préparation) : `LSTM_MODEL_DIR` — une variable d'environnement, suivant
exactement le même principe que `DATABASE_URL`/`CORS_ALLOWED_ORIGINS` déjà
dans le projet — pointe vers un chemin absolu sur le **disque persistant**
Render (survit aux redéploiements, contrairement au reste du système de
fichiers du conteneur).

### Procédure (une seule fois après le premier déploiement)

1. Attacher un disque persistant au service Render (`render.yaml` en déclare
   un, monté sur `/var/data`, 1 Go — largement suffisant : les 12 modèles
   font ~45 Ko chacun).
2. Depuis l'onglet **Shell** de Render (ou `render ssh` en CLI), créer le
   répertoire : `mkdir -p /var/data/lstm_models`.
3. Transférer les fichiers depuis votre machine (où ils ont déjà été
   entraînés — voir [Modèles LSTM](README.md#modèles-lstm)) :
   `scp -r trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs/* <shell-render>:/var/data/lstm_models/`
   (l'onglet Shell de Render affiche la commande `ssh`/`scp` exacte pour
   votre service).
4. Vérifier : redémarrer le service et consulter les logs — le message déjà
   existant au démarrage (`[optiport] LSTM models found: N (...)`) confirme
   que les 12 modèles sont détectés à l'endroit attendu.

**Alternative sans disque persistant** (si vous préférez ne pas payer pour
un disque, ou pour un déploiement reproductible sans étape manuelle) :
uploader une archive des modèles vers un stockage objet externe (S3, GCS,
Cloudflare R2, ou même une Release GitHub privée) une fois après
entraînement local, puis remplacer la commande de démarrage par un petit
script qui télécharge et extrait l'archive si `/var/data/lstm_models` (ou un
répertoire local temporaire) est vide, avant de lancer `uvicorn`. Non
implémenté ici — dépend du fournisseur de stockage que vous choisiriez, ce
qui n'était pas spécifié ; l'option disque persistant ci-dessus est la plus
simple et ne demande aucune infrastructure supplémentaire.

**Dans les deux cas, aucun autre changement de code n'est nécessaire** : le
backend démarre normalement même sans modèles (repli déjà existant sur le
dernier rendement observé) et les détecte automatiquement dès qu'ils
apparaissent au chemin configuré, au prochain redémarrage.

---

## 5. SQLite + WAL sur le disque persistant Render — limite qui compte réellement

**Le disque persistant est obligatoire, pas optionnel, pour cette
architecture.** Sans lui (plan gratuit Render, qui ne propose pas de disque
persistant), `optiport.db` vivrait sur le système de fichiers éphémère du
conteneur — **toutes les données (comptes, portefeuilles, ordres) seraient
perdues à chaque redéploiement et probablement à chaque redémarrage**. Le
plan gratuit Render met aussi le service en veille après inactivité (~15
min) puis le redémarre à la requête suivante — chaque réveil sur le plan
gratuit reproduirait cette perte de données. Un plan payant avec disque
persistant est donc requis pour que "SQLite + WAL pour le MVP actuel" soit
réellement viable en production, pas seulement en théorie.

**Ce qui est déjà correct** (audit de production readiness précédent) :
`PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL` sont déjà activés
par connexion dans `backend/db.py`, permettant les lectures concurrentes
pendant qu'une écriture est en cours — pertinent dès que plusieurs
utilisateurs sont actifs simultanément, ce qui sera le cas dès la mise en
production.

**Limite propre à WAL sur un disque réseau/monté** : le mode WAL suppose que
les verrous fichier (`flock`) fonctionnent correctement sur le système de
fichiers sous-jacent. Les disques persistants Render sont des volumes de
bloc standards (pas un montage réseau type NFS) donc ce n'est pas un
problème connu ici — à mentionner uniquement si vous migriez un jour vers un
stockage réseau partagé, ce qui n'est pas le cas de cette architecture.

**Migration PostgreSQL** : non nécessaire maintenant, comme demandé — SQLite
+ disque persistant + WAL suffit pour un seul processus backend (Render ne
permet de toute façon pas de partager un disque persistant entre plusieurs
instances d'un même service, donc SQLite ne bloque pas non plus un futur
scaling vertical — seul un scaling *horizontal*, plusieurs instances
backend simultanées, nécessiterait Postgres, et rien dans l'architecture
cible actuelle ne le demande).

---

## 6. Résilience aux pannes externes — déjà vérifié, rappel

Déjà confirmé lors de l'audit de production précédent (aucun changement ici) :
Yahoo Finance, NewsAPI, Groq et les modèles LSTM dégradent tous proprement
(codes HTTP explicites, jamais de crash process) — voir la section
correspondante du [README](README.md#résilience-aux-pannes-de-services-externes).
Rien de spécifique à Render/Vercel ne change ce comportement.

---

## 7. Checklist de déploiement

### Avant le premier déploiement

- [ ] Générer un `AUTH_SECRET_KEY` de production (jamais réutiliser celui du
      `.env` local)
- [ ] Avoir sous la main : clé NewsAPI, clé Groq
- [ ] Avoir les 12 fichiers `.keras` + `scalers.pkl` entraînés localement
      disponibles pour transfert (voir [Modèles LSTM](README.md#modèles-lstm)
      si besoin de les régénérer)
- [ ] Si "Continue with Google" est souhaité : créer un client OAuth
      "Web application" sur console.cloud.google.com, noter le Client ID
      et le Client Secret — l'Authorized redirect URI exacte (elle pointe
      vers ce backend, pas vers Vercel) ne pourra être ajoutée qu'après le
      premier déploiement Render (elle dépend de son URL)

### Backend (Render)

- [ ] Créer le service web avec `render.yaml` (Blueprint) ou manuellement
      avec les commandes de build/démarrage de la section 2
- [ ] Choisir un plan supportant un disque persistant (pas le plan gratuit)
- [ ] Renseigner toutes les variables `sync: false` dans le tableau de bord :
      `AUTH_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, `NEWS_API_KEY`, `GROQ_API_KEY`
- [ ] Premier déploiement — vérifier les logs pour
      `Application startup complete` et le message LSTM (probablement
      "not found" à ce stade, avant le transfert des modèles)
- [ ] Transférer les modèles vers le disque persistant (section 4)
- [ ] Redémarrer le service, vérifier `[optiport] LSTM models found: 12`
      dans les logs
- [ ] Depuis le Shell Render, créer le premier compte admin :
      `python -m backend.create_admin` (avec `ADMIN_*` définis, ou en
      interactif)
- [ ] Vérifier `GET https://<votre-service>.onrender.com/health` → `200`
- [ ] Vérifier `GET https://<votre-service>.onrender.com/docs` → Swagger UI
- [ ] Si "Continue with Google" : maintenant que l'URL Render est connue,
      ajouter `https://<votre-service>.onrender.com/auth/google/callback`
      comme Authorized redirect URI sur le client OAuth Google, puis définir
      `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REDIRECT_URI` sur
      Render avec cette même URL et redéployer

### Frontend (Vercel)

- [ ] Importer le dépôt, Root Directory = `frontend`
- [ ] Définir `VITE_API_BASE_URL` = URL du service Render
- [ ] Déployer, vérifier que `frontend/vercel.json` est bien détecté
      (routes profondes comme `/app/dashboard` ne doivent pas renvoyer 404
      après un rafraîchissement)

### Après déploiement des deux — vérification croisée

- [ ] Mettre à jour `CORS_ALLOWED_ORIGINS` sur Render avec l'URL Vercel
      réelle (générée après le premier déploiement Vercel), puis redéployer
- [ ] Si "Continue with Google" : définir `FRONTEND_URL` sur Render avec
      l'URL Vercel réelle, puis redéployer le backend, puis tester le
      bouton en conditions réelles (il doit apparaître sur Login uniquement
      une fois `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REDIRECT_URI`
      définis — `GOOGLE_REDIRECT_URI` pointe déjà vers Render depuis le
      premier déploiement, voir section 3, et n'a pas besoin de changer ici)
- [ ] Tester le flux complet en conditions réelles : inscription → connexion
      → Markets → Trading → Analytics/Smart Invest → News → AI Assistant →
      déconnexion, en observant la console navigateur (aucune erreur CORS)
- [ ] Confirmer qu'un rafraîchissement de page sur une route profonde
      (`/app/portfolio`) fonctionne (test direct du `vercel.json`)

---

## 8. Ce qui n'est délibérément pas fait ici

- Rien n'a été déployé — ce document et les fichiers de configuration
  préparent le déploiement, ne l'exécutent pas.
- Pas de migration vers PostgreSQL (non nécessaire, voir section 5).
- Pas de script de téléchargement automatique des modèles depuis un stockage
  objet externe (dépend d'un fournisseur non spécifié — voir l'alternative
  documentée en section 4 si vous choisissez cette voie plus tard).
- Pas de CI/CD (GitHub Actions, etc.) — explicitement hors périmètre de
  cette tâche (« Do NOT work on GitHub »).
