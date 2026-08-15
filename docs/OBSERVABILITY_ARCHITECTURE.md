# 📊 Architecture d'Observabilité, Logging, Replay & Analytics — Piloteer

Ce document détaille l'implémentation complète du système d'observabilité de **Piloteer**, couvrant la capture des événements asynchrones, le schéma de base de données SQLite, le visualiseur de Replay pas-à-pas et le tableau de bord de performance analytique.

---

## 1. Vue d'Ensemble de l'Architecture

Le sous-système d'observabilité est divisé en deux modules complémentaires :
1. **`src/loggings/` (Couche d'Ingestion & Stockage)** : Enregistre de manière asynchrone chaque décision d'IA, capture d'écran, métrique de latence et consommation de tokens sans bloquer l'agent.
2. **`src/administration/` (Couche de Restitution & Visualisation)** : Fournit des interfaces d'analyse (Streamlit) pour inspecter l'historique complet des missions (*Replay*) et mesurer la performance globale (*Metrics*).

```
┌─────────────────────────────────────────────────────────────┐
│                 PIPELINE AGENT (LangGraph)                  │
│       TaskDirector  ➔  Planner  ➔  Actor  ➔  Validator      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Appel asynchrone non-bloquant
                               │ asyncio.create_task(log_event(...))
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  MOTEUR D'INGESTION (logger.py)             │
│   - Calcul durée (duration_ms)                              │
│   - Sérialisation JSON du payload (raisonnement, action)    │
│   - Exécution SQLite via loop.run_in_executor               │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐
│  DATABASE (piloteer_logs.db) │ │ SCREENSHOTS (screenshots/)  │
│  Table SQLite 'events'      │ │ 1 PNG par étape Actor       │
└──────────────┬──────────────┘ └──────────────┬──────────────┘
               │                               │
               └───────────────┬───────────────┘
                               │ Requêtes SQL (Pandas)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             INTERFACE ADMIN & REPLAY (app.py)               │
│   - Session Replay (Step-by-step viewer + Captures d'écran) │
│   - Performance Dashboard (KPIs, Tokens, Latences, Graphes) │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Le Schéma de Données (`events` Table)

Fichier : `src/loggings/scripts/schema.py`  
Base : `src/loggings/database/piloteer_logs.db`

La granularité est **atomique** : chaque exécution de nœud (un passage dans le TaskDirector, une décision du Planner, un clic de l'Actor, une vérification du Validator) génère **une ligne unique** dans la table `events`.

| Colonne | Type | Description |
| :--- | :--- | :--- |
| `event_id` | `INTEGER PK` | Identifiant incrémental unique de l'événement. |
| `trace_id` | `TEXT` | Identifiant global de la session / mission utilisateur. |
| `subgoal_id` | `TEXT` | Identifiant du sous-objectif (ex: `subgoal_000`, `subgoal_001`). |
| `step_id` | `TEXT` | Identifiant composite de l'étape (ex: `subgoal_000_step_002`). |
| `node_name` | `TEXT` | Nom du composant LangGraph (`task_director`, `planner`, `actor`, `validator`). |
| `phase` | `TEXT` | Sous-phase contextuelle (ex: `understand`, `understand_fast`, `revise`, `finalize`). |
| `status` | `TEXT` | Résultat de l'étape (`success`, `error`, `needs_revision`, `blocked`). |
| `timestamp_start` | `TEXT` | Horodatage ISO-8601 UTC du début de l'exécution du nœud. |
| `timestamp_end` | `TEXT` | Horodatage ISO-8601 UTC de fin de l'exécution. |
| `duration_ms` | `INTEGER` | Durée d'exécution du nœud en millisecondes. |
| `gen_ai_model` | `TEXT` | Nom précis du modèle LLM appelé (ex: `gemini-2.5-flash`, `gemini-3.5-flash`). |
| `gen_ai_input_tokens` | `INTEGER` | Nombre de tokens d'entrée (prompt) consommés. |
| `gen_ai_output_tokens`| `INTEGER` | Nombre de tokens générés (réponse) par le LLM. |
| `payload` | `TEXT (JSON)` | Raisonnement complet, arguments de l'action ou verdict structuré. |
| `screenshot` | `TEXT` | Chemin absolu vers le fichier PNG capturé sur disque. |

---

## 3. Mécanisme de Logging Asynchrone (`logger.py`)

Fichier : `src/loggings/scripts/logger.py`

### Points Clés de Conception :
1. **Zéro Latence sur l'Agent** : La fonction `log_event(...)` est appelée de manière asynchrone (`asyncio.create_task(...)` ou `run_in_executor`). Le pipeline LangGraph continue son exécution sans attendre l'écriture disque.
2. **Gestion Optimisée des Images** : Les captures d'écran ne sont jamais stockées sous forme de BLOB dans SQLite (ce qui alourdirait la base de données). Elles sont écrites sous forme de fichiers PNG dans `src/loggings/screenshots/run_<trace_id>/`, et seul le chemin est enregistré.
3. **Capture d'État Unique** : La capture d'écran est prise uniquement par le nœud **Actor** immédiatement *avant* d'exécuter l'action sur le navigateur. La capture avant l'étape $N$ sert naturellement d'état "après" pour l'étape $N-1$.

---

## 4. Module de Replay Pas-à-Pas (`replay.py`)

Fichier : `src/administration/replay/replay.py`

Le Replay permet de rejouer mentalement et visuellement n'importe quelle mission passée :

### Fonctionnalités :
- **Sélecteur de Mission (`trace_id`)** : Permet de choisir une mission parmi toutes celles exécutées.
- **Barre de Navigation Temporelle** :
  - Boutons `[First]`, `[Previous]`, `[Next]`, `[Last]`.
  - Compteur d'étape dynamique (`Step X of Y`).
  - Badges visuels indiquant le **Nœud actif** (violet) et le **Statut** (vert `success` / rouge `error`).
- **Vue Double Colonne (Écran vs Cerveau)** :
  - **Colonne Gauche (Screenshot)** : Affiche l'image exacte de la page web au moment précis où l'agent a pris sa décision.
  - **Colonne Droite (Raisonnement IA)** :
    - 3 compteurs métriques : Durée (`ms`), Tokens d'entrée, Tokens de sortie.
    - JSON interactif et dépliable contenant le raisonnement étape par étape (ex: `1_analyze_subgoal`, `2_inspect_snapshot`, `3_choose_action`, `4_make_decision`).

---

## 5. Tableau de Bord de Performance (`performance.py`)

Fichier : `src/administration/performance/performance.py`

Ce tableau de bord analytique agrège les données brutes pour évaluer l'efficacité et les coûts de l'agent.

### Métriques et Graphiques Disponibles :
1. **Filtre de Portée (Scope Selector)** :
   - Analyser **Toutes les missions** confondues ou **Une mission spécifique**.
2. **KPIs Globaux (Cartes Synthétiques)** :
   - Nombre total de missions (`Missions`).
   - Volume total de tokens d'entrée (`Input Tokens`).
   - Volume total de tokens de sortie (`Output Tokens`).
   - Temps total passé en secondes (`Total Duration`).
   - Nombre d'actions réussies (`Successes`).
   - Taux de réussite global (`Success Rate %`).
3. **Tableau Analytique par Nœud (`Breakdown by Node`)** :
   - Nombre d'appels par composant (`task_director`, `planner`, `actor`, `validator`).
   - Tokens consommés par composant.
   - Durée moyenne et totale par composant.
   - Taux de succès par composant.
4. **Graphiques Visuels Comparatifs** :
   - **Graphe 1** : Consommation de tokens (Entrée vs Sortie) par nœud.
   - **Graphe 2** : Temps d'exécution moyen par nœud (détecte quel composant ralentit le système).
5. **Tableau Récapitulatif par Mission** :
   - Vue tabulaire classant chaque mission avec son nombre d'étapes, son coût en tokens, sa durée totale et son taux de complétion.

---

## 6. Architecture Actuelle vs Future (Streamlit vs Next.js)

| Critère | Implémentation Actuelle (Streamlit) | Évolution Next.js Proposée |
| :--- | :--- | :--- |
| **Serveur & Port** | Serveur Python dédié sur `localhost:8501` | Intégré dans l'application Next.js sur `/admin` (`localhost:3000/admin`) |
| **Source de Données** | Lecture directe SQL dans `piloteer_logs.db` | Endpoints REST FastAPI (`GET /api/admin/traces`, `GET /api/admin/replay/{id}`) |
| **Design & Cohérence** | Thème standard Streamlit | Design Tailwind CSS moderne, composants graphiques interactifs (Recharts) |
| **Déploiement** | 2 serveurs séparés (FastAPI + Streamlit) | Architecture unifiée Frontend Client + Backend API |
