# Optimisations et Décisions Architecturales Futures

Ce document recense les failles identifiées dans l'architecture actuelle de Piloteer et les solutions d'optimisation proposées, basées sur les meilleures pratiques et la recherche actuelle sur les agents LLM autonomes (Plan-and-Solve). Ces éléments doivent être implémentés pour améliorer les performances, la latence et les coûts.

## 1. L'engorgement de la Mémoire (Context Bloat)

**Problème :**
Dans le `planner_prompt`, la variable `memory_str` est injectée à chaque itération. Si un essai nécessite de nombreuses étapes (ex: 15 étapes), cette chaîne de mémoire s'allonge considérablement. Un contexte trop grand ralentit le temps de génération du LLM (latence d'inférence) et augmente les coûts de l'API.

**Recherche associée :**
La recherche sur les agents autonomes montre que les fenêtres de contexte surchargées conduisent au problème du "Lost in the middle" (le modèle oublie ou ignore les informations critiques au milieu du prompt) et dégradent les performances de prise de décision.

**Décision / Solution à implémenter :**
Ajouter un **Résumé Dynamique (Memory Summarizer)**. Au lieu de conserver l'historique complet de toutes les actions, le système doit compacter l'historique pour ne garder que les 3 dernières actions pertinentes en format brut, tout en générant un résumé synthétique des actions plus anciennes.

---

## 2. Le Poids des Snapshots pour le Validateur (Validation Latency)

**Problème :**
Le `Validator` reçoit l'arbre d'accessibilité COMPLET d'avant et d'après l'action. Même après élagage (environ 2 000 tokens par arbre), cela représente 4 000 tokens à analyser à *chaque* itération de validation. Cela crée un goulot d'étranglement majeur en termes de vitesse.

**Recherche associée :**
Les tâches d'évaluation (comme la validation d'état) sont beaucoup plus efficaces lorsque le ratio signal/bruit est élevé. Envoyer des pages entières non modifiées noie l'attention du LLM.

**Décision / Solution à implémenter :**
Faire un **"Diff" programmatique**. Implémenter une fonction Python qui compare l'arbre d'accessibilité `snapshot_before` et `snapshot_after`. Au lieu d'envoyer les deux arbres complets au LLM, le système n'enverra au `Validator` que les nœuds (et leurs parents proches) qui ont subi un changement (ajout, suppression, modification d'état). La vitesse de validation explosera et le coût chutera.

---

## 3. Latence de la Boucle Stricte "Un seul pas" (Action Batching)

**Problème :**
L'architecture actuelle impose une boucle stricte : `Planner -> Actor -> Validator` pour *chaque* petite action (ex: un seul clic, une seule frappe). Si le LLM prend 3 secondes par inférence, une simple tâche comme taper un email, taper un mot de passe, et cliquer sur 'Connexion' nécessitera 3 itérations complètes (9 à 15 secondes minimum). Bien que très sûr, c'est extrêmement lent pour des actions prévisibles.

**Recherche associée :**
Les architectures "Step-wise Greedy" qui limitent l'agent à une action unitaire sont robustes face aux changements dynamiques de l'environnement, mais inefficaces. Les frameworks avancés utilisent le **Macro-Action Batching**, permettant à l'agent d'émettre des séquences d'actions si son niveau de confiance sur la stabilité de l'UI est élevé.

**Décision / Solution à implémenter :**
Permettre au `Planner` d'émettre des **mini-séquences d'actions** (ex: `[type_email, type_password, click_login]`) dans un seul tableau JSON lorsqu'il fait face à un formulaire ou à une suite d'actions évidentes. L'Actor exécutera la séquence, et le Validator ne vérifiera le résultat qu'à la fin de la séquence. Si l'état de la page est incertain, le Planner reviendra automatiquement à l'émission d'une seule action.

---

## 4. Biais de Conformité et Manque de Vérification Macro (Macro-Level Verification)

**Problème :**
Actuellement, lorsque le `Validator` (agent de bas niveau) valide un sous-objectif (`subgoal_done: true`), le système LangGraph passe immédiatement au sous-objectif suivant. Le `High-Level Planner` n'est jamais consulté pour confirmer ce succès. Si le `Validator` hallucine un succès, l'agent poursuit son exécution sur une page incorrecte, provoquant des échecs en cascade impossibles à rattraper.

**Recherche associée :**
La recherche sur les systèmes multi-agents (MAS) met en garde contre le **"Biais de Conformité" (Conformity Bias)** et "l'illusion de conformité", où l'absence de regard critique indépendant mène à l'accumulation d'erreurs (Error Propagation). Les architectures modernes exigent une **Validation de Trajectoire (Trajectory-Level Validation)** indépendante pour vérifier l'alignement avec l'intention globale (Macro-niveau), et non pas seulement la réussite d'un clic ou d'une action locale (Micro-niveau).

**Décision / Solution à implémenter :**
Créer un nœud indépendant **`Macro_Verifier` (ou Juge Global)** dans LangGraph. Ce nœud n'interviendra qu'à la fin supposée d'un sous-objectif. Il recevra le `snapshot` de la page et le `user_task` global, avec pour consigne stricte de chercher la *preuve visuelle* du succès, de manière "sceptique". Si le `Macro_Verifier` rejette le succès, le sous-objectif n'est pas validé et une escalade (ou révision) est déclenchée.
