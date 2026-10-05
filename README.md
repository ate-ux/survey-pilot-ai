# SurveyPilot AI V2

Plateforme d'enquêtes statistiques multi-projets avec IA, géolocalisation et analyse avancée.

## 🌐 Application en ligne

**Interface** : https://survey-pilot-frontend.onrender.com
**API (Swagger)** : https://survey-pilot-ai.onrender.com/docs

**Identifiants démo** : `admin` / `admin123`

## 🚀 Fonctionnalités

### Gouvernance
- Authentification JWT avec rôles (Super Admin, Gestionnaire, Analyste, Enquêteur)
- Journal d'audit complet de toutes les actions
- Gestion des utilisateurs (création, activation, suppression)
- Profil utilisateur (nom, email, mot de passe, photo)

### Enquêtes & Collecte
- CRUD Projets, Enquêtes, Questions, Réponses
- Import CSV de données
- Échantillonnage avancé :
  - Tirage aléatoire simple
  - Tirage systématique (1 sur k)
  - Tirage stratifié
  - Tirage par grappes (clusters)
  - Tirage multi-degrés
  - Allocation optimale (proportionnelle, Neyman, égale)
- Calcul de taille d'échantillon avec marge d'erreur

### IA & Analyse
- **Agents IA** : Méthodologue, Échantillonneur (règles métier)
- **LLM Groq** (GPT-OSS 120B) pour recommandations automatiques
- **Machine Learning** :
  - Isolation Forest (détection d'anomalies)
  - Random Forest (prédiction de non-réponse)
  - Profil des données
- Analyse statistique : descriptives, corrélations, régression

### Géolocalisation
- Zones géographiques (ISSEA, quartiers, régions)
- Carte interactive (OpenStreetMap)
- Coordonnées GPS sur les réponses
- Suivi des enquêteurs
- Requêtes "réponses proches" (Haversine)

### Gouvernance avancée
- Sandbox (environnement isolé)
- Versioning (snapshots et restauration)
- Base de connaissances
- Workflow d'approbation (Human-in-the-Loop)

## 🏗️ Architecture
