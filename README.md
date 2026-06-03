# MCP Moodle Server — RTN

> Serveur **Model Context Protocol (MCP)** pour la plateforme Moodle,  
> construit avec **FastMCP 3.x** et le transport **streamable-http**.  
> Expose 115 outils couvrant l'ensemble de l'API Web Service de Moodle.

---

## Table des matières

- [Aperçu](#aperçu)
- [Prérequis](#prérequis)
- [Installation rapide](#installation-rapide)
- [Configuration](#configuration)
- [Déploiement en production](#déploiement-en-production)
  - [Service systemd](#service-systemd)
  - [Nginx reverse proxy + SSL](#nginx-reverse-proxy--ssl)
- [Connexion à Claude Desktop](#connexion-à-claude-desktop)
- [Liste des outils (115)](#liste-des-outils-115)
- [Obtenir le token Moodle](#obtenir-le-token-moodle)
- [Dépannage](#dépannage)
- [Licence](#licence)

---

## Aperçu

Ce serveur MCP permet à tout client MCP (Claude Desktop, agents IA, etc.) de piloter
une instance Moodle via son API Web Service REST.

```
Client MCP (Claude)  ←→  https://votre-domaine.com/mcp  ←→  Moodle API
```

**Caractéristiques :**
- Transport `streamable-http` (MCP 2024-11-05)
- 115 outils organisés par domaine fonctionnel
- Authentification par token Moodle (Web Service token)
- Compatible Moodle 4.x
- Déploiement via systemd + nginx + Let's Encrypt

---

## Prérequis

| Composant | Version minimale |
|-----------|-----------------|
| Python | 3.10+ |
| pip | 22+ |
| nginx | 1.18+ |
| certbot (snap) | any |
| Moodle | 4.0+ |
| Système | Ubuntu 20.04+ / Debian 11+ |

Vérifier :
```bash
python3 --version
nginx -v
```

---

## Installation rapide

```bash
# 1. Cloner le dépôt
git clone https://github.com/Sergio-Oracle/mcp-moodle.git
cd mcp-moodle

# 2. Installer les dépendances Python
pip3 install fastmcp httpx python-dotenv

# 3. Copier et éditer la configuration
cp .env.example .env
nano .env
```

---

## Configuration

Éditer le fichier `.env` :

```env
# URL de votre instance Moodle (sans slash final)
MOODLE_URL=https://e-learning.votre-domaine.com

# Token Web Service Moodle (voir section "Obtenir le token Moodle")
MOODLE_TOKEN=VOTRE_TOKEN_ICI

# Port interne du serveur MCP (nginx proxyfiera depuis ce port)
MCP_PORT=8090
```

Tester la configuration :
```bash
python3 server.py
# Le serveur démarre sur http://0.0.0.0:8090/mcp
```

Vérifier que Moodle répond :
```bash
curl -s -X POST http://localhost:8090/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' \
  | grep sitename
```

---

## Déploiement en production

### Service systemd

Copier le fichier de service :

```bash
sudo cp mcp-moodle.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mcp-moodle
sudo systemctl start mcp-moodle
sudo systemctl status mcp-moodle
```

Contenu de `mcp-moodle.service` :

```ini
[Unit]
Description=RTN Moodle MCP Server (FastMCP 3.x)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/mcp-moodle
EnvironmentFile=/root/mcp-moodle/.env
ExecStart=/usr/bin/python3 /root/mcp-moodle/server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mcp-moodle

[Install]
WantedBy=multi-user.target
```

> **Adapter `WorkingDirectory` et `EnvironmentFile`** selon le chemin d'installation réel.

---

### Nginx reverse proxy + SSL

#### 1. Créer le certificat SSL (Let's Encrypt)

```bash
# Installer certbot via snap (recommandé)
sudo snap install --classic certbot

# Config nginx temporaire pour la validation HTTP
sudo tee /etc/nginx/sites-available/mcp > /dev/null << 'EOF'
server {
    listen 80;
    server_name mcp.votre-domaine.com;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$host$request_uri; }
}
EOF

sudo ln -sf /etc/nginx/sites-available/mcp /etc/nginx/sites-enabled/mcp
sudo nginx -t && sudo nginx -s reload

# Obtenir le certificat
sudo certbot certonly --webroot -w /var/www/html \
  -d mcp.votre-domaine.com \
  --email votre@email.com --agree-tos --non-interactive
```

#### 2. Configurer nginx avec HTTPS

Copier le fichier de configuration nginx :

```bash
# Adapter le nom de domaine dans le fichier
sed 's/mcp.rtn.sn/mcp.votre-domaine.com/g' nginx-mcp.conf \
  | sudo tee /etc/nginx/sites-available/mcp > /dev/null

sudo nginx -t && sudo nginx -s reload
```

Contenu de `nginx-mcp.conf` (inclus dans ce dépôt) :

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name mcp.votre-domaine.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name mcp.votre-domaine.com;

    ssl_certificate     /etc/letsencrypt/live/mcp.votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.votre-domaine.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    access_log /var/log/nginx/mcp-access.log;
    error_log  /var/log/nginx/mcp-error.log;

    proxy_read_timeout    300s;
    proxy_send_timeout    300s;
    proxy_connect_timeout 10s;

    location /mcp {
        proxy_pass         http://127.0.0.1:8090/mcp;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        $connection_upgrade;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_buffering    off;
        proxy_cache        off;
        add_header Access-Control-Allow-Origin  * always;
        add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS' always;
        add_header Access-Control-Allow-Headers 'Content-Type, Authorization, Accept, Mcp-Session-Id' always;
        if ($request_method = OPTIONS) { return 204; }
    }

    location / {
        return 200 'MCP Moodle Server OK — endpoint: https://mcp.votre-domaine.com/mcp';
        add_header Content-Type text/plain;
    }
}
```

#### 3. Vérifier le déploiement

```bash
# Test HTTPS depuis n'importe quelle machine
curl -s -X POST https://mcp.votre-domaine.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' \
  | python3 -m json.tool
```

Réponse attendue :
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "serverInfo": { "name": "RTN Moodle", "version": "3.4.0" }
  }
}
```

---

## Connexion à Claude Desktop

Ajouter dans `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows) :

```json
{
  "mcpServers": {
    "moodle": {
      "type": "streamable-http",
      "url": "https://mcp.votre-domaine.com/mcp"
    }
  }
}
```

Redémarrer Claude Desktop. Les 115 outils Moodle apparaissent automatiquement.

---

## Obtenir le token Moodle

1. Connectez-vous à Moodle en tant qu'administrateur
2. **Administration du site** → **Plugins** → **Services web** → **Gérer les jetons**
3. Cliquer **Ajouter**
4. Sélectionner l'utilisateur et le service (ex. "MCP Service")
5. Copier le token généré → coller dans `.env`

> Le service web doit avoir les fonctions correspondantes aux outils activés.  
> Voir **Administration du site → Plugins → Services web → Services externes → Fonctions**.

---

## Liste des outils (115)

### Site & Authentification
| Outil | Description |
|-------|-------------|
| `get_site_info` | Infos du site et de l'utilisateur connecté |
| `confirm_user` | Confirmer un compte utilisateur |
| `request_password_reset` | Demander réinitialisation mot de passe |

### Utilisateurs
| Outil | Description |
|-------|-------------|
| `create_users` | Créer des utilisateurs |
| `get_users` | Rechercher des utilisateurs |
| `get_users_by_field` | Récupérer par champ unique (id, email…) |
| `update_users` | Mettre à jour des utilisateurs |
| `delete_users` | Supprimer des utilisateurs |
| `get_course_user_profiles` | Profils dans le contexte d'un cours |
| `view_user_list` | Vue liste utilisateurs d'un cours |
| `view_user_profile` | Vue profil d'un utilisateur |
| `add_user_private_files` | Copier fichiers vers espace privé |

### Cours & Catégories
| Outil | Description |
|-------|-------------|
| `get_courses` | Détails des cours |
| `search_courses` | Recherche par nom, module, bloc, tag |
| `create_courses` | Créer des cours |
| `update_courses` | Mettre à jour des cours |
| `get_course_contents` | Contenu d'un cours (sections, modules) |
| `get_categories` | Catégories de cours |
| `create_categories` | Créer des catégories |
| `update_categories` | Mettre à jour des catégories |
| `delete_categories` | Supprimer des catégories |
| `get_recent_courses` | Cours récemment accédés |
| `get_enrolled_users_by_cmid` | Inscrits d'un module de cours |
| `edit_course_module` | Action sur un module (hide, show, delete…) |
| `get_courseformat_file_handlers` | Gestionnaires de fichiers du format de cours |

### Inscriptions
| Outil | Description |
|-------|-------------|
| `get_course_enrolment_methods` | Méthodes d'inscription d'un cours |
| `get_enrolled_users` | Utilisateurs inscrits à un cours |
| `get_enrolled_users_with_capability` | Inscrits avec une capacité spécifique |
| `enrol_users` | Inscrire manuellement des utilisateurs |
| `unenrol_users` | Désinscrire des utilisateurs |

### Notes & Bulletins
| Outil | Description |
|-------|-------------|
| `get_grade_tree` | Arbre des notes d'un cours |
| `update_grades` | Mettre à jour des notes |
| `get_users_in_grader_report` | Utilisateurs dans le rapport de notes |
| `get_course_grades_overview` | Notes finales de l'utilisateur courant |
| `get_grade_items_for_user` | Items de notes pour un utilisateur |
| `get_grades_table` | Tableau des notes |
| `get_grade_items_for_search_widget` | Items pour widget de recherche |
| `get_user_grade_report_access` | Accès au rapport de notes |
| `view_grade_report_overview` | Déclencher événement vue rapport global |
| `view_grade_report_user` | Déclencher événement vue rapport utilisateur |

### Groupes
| Outil | Description |
|-------|-------------|
| `create_groups` | Créer des groupes |
| `add_group_members` | Ajouter des membres à un groupe |
| `get_course_groups` | Groupes d'un cours |

### Fichiers
| Outil | Description |
|-------|-------------|
| `get_files` | Parcourir les fichiers Moodle |
| `get_unused_draft_itemid` | Générer un itemid de brouillon |
| `delete_draft_files` | Supprimer des fichiers brouillon |

### Calendrier
| Outil | Description |
|-------|-------------|
| `get_calendar_events` | Événements du calendrier |
| `get_action_events_by_course` | Événements d'action pour un cours |

### Compétences & Plans d'apprentissage
| Outil | Description |
|-------|-------------|
| `create_competency` | Créer une compétence |
| `create_learning_plan` | Créer un plan d'apprentissage |
| `complete_learning_plan` | Marquer un plan comme complété |
| `read_learning_plan` | Lire un plan d'apprentissage |
| `list_user_learning_plans` | Plans d'un utilisateur |
| `create_competency_template` | Créer un template de plan |
| `count_competency_templates` | Compter les templates |

### Complétion & Contenu
| Outil | Description |
|-------|-------------|
| `get_course_completion_status` | Statut de complétion d'un cours |
| `copy_content` | Copier un contenu dans la banque de contenu |
| `create_custom_field_category` | Créer une catégorie de champ personnalisé |

### Annotations & Messagerie
| Outil | Description |
|-------|-------------|
| `create_notes` | Créer des annotations sur des utilisateurs |
| `get_course_notes` | Annotations d'un cours |
| `get_blocked_users` | Utilisateurs bloqués |

### Questions
| Outil | Description |
|-------|-------------|
| `get_random_question_summaries` | Questions aléatoires selon critères |
| `update_question_flag` | Mettre à jour le flag d'une question |

### Quiz — Plugin local_mcp (RTN)
> Fonctions personnalisées du plugin `local_mcp_quiz` développé par RTN.

| Outil | Description |
|-------|-------------|
| `mcp_create_quiz` | Créer un quiz |
| `mcp_create_question_category` | Créer une catégorie de questions |
| `mcp_create_multichoice_question` | Créer une question à choix multiple |
| `mcp_create_shortanswer_question` | Créer une question à réponse courte |
| `mcp_create_truefalse_question` | Créer une question Vrai/Faux |
| `mcp_add_question_to_quiz` | Ajouter une question à un quiz |

### Forum
| Outil | Description |
|-------|-------------|
| `get_forums_by_courses` | Forums d'une liste de cours |
| `get_forum_discussions` | Discussions d'un forum |
| `add_forum_discussion` | Créer une discussion |
| `add_forum_discussion_post` | Répondre dans une discussion |

### Devoirs (Assignment)
| Outil | Description |
|-------|-------------|
| `get_assignments` | Devoirs accessibles |
| `get_assignment_submissions` | Soumissions de devoirs |
| `get_assignment_submission_status` | Statut de soumission d'un devoir |
| `get_assignment_grades` | Notes de devoirs |
| `save_assignment_grade` | Sauvegarder une note de devoir |
| `list_assignment_participants` | Participants à un devoir |

### Quiz (mod_quiz — 37 outils)
| Outil | Description |
|-------|-------------|
| `get_quizzes_by_courses` | Liste des quiz dans des cours |
| `get_quiz_access_information` | Informations d'accès à un quiz |
| `start_quiz_attempt` | Démarrer une tentative |
| `get_quiz_attempt_data` | Données d'une page de tentative |
| `save_quiz_attempt` | Auto-sauvegarder une tentative |
| `process_quiz_attempt` | Traiter les réponses / terminer |
| `get_quiz_attempt_summary` | Résumé avant soumission |
| `get_quiz_attempt_review` | Révision d'une tentative terminée |
| `get_quiz_attempt_access_information` | Accès à une tentative |
| `get_user_quiz_attempts` | Tentatives d'un utilisateur |
| `get_user_best_quiz_grade` | Meilleure note |
| `get_quiz_combined_review_options` | Options de révision |
| `get_quiz_feedback_for_grade` | Feedback pour une note |
| `get_quiz_required_qtypes` | Types de questions requis |
| `view_quiz` | Déclencher événement vue quiz |
| `view_quiz_attempt` | Déclencher événement vue tentative |
| `view_quiz_attempt_summary` | Déclencher événement vue résumé |
| `view_quiz_attempt_review` | Déclencher événement révision |
| `get_quiz_overrides` | Exceptions d'un quiz |
| `save_quiz_overrides` | Sauvegarder des exceptions |
| `delete_quiz_overrides` | Supprimer des exceptions |
| `get_reopen_attempt_confirmation` | Vérifier réouverture tentative |
| `reopen_quiz_attempt` | Rouvrir une tentative abandonnée |
| `create_quiz_grade_items` | Créer des items de note |
| `create_quiz_grade_item_per_section` | Item de note par section |
| `update_quiz_grade_items` | Mettre à jour items de note |
| `delete_quiz_grade_items` | Supprimer items de note |
| `add_random_questions_to_quiz` | Ajouter questions aléatoires |
| `get_quiz_edit_grading_page` | Page de configuration notation |
| `update_quiz_slots` | Mettre à jour slots du quiz |
| `set_quiz_question_version` | Définir version d'une question |
| `update_quiz_filter_condition` | Condition de filtre slot aléatoire |

### Divers
| Outil | Description |
|-------|-------------|
| `get_resources_by_courses` | Ressources (fichiers) dans des cours |
| `get_recent_items` | Éléments récemment accédés |
| `send_activity_to_moodlenet` | Partager vers MoodleNet |
| `delete_xapi_state` | Supprimer un état xAPI |

---

## Dépannage

### Le serveur ne démarre pas

```bash
# Voir les logs
journalctl -u mcp-moodle -n 50 --no-pager

# Vérifier la syntaxe Python
python3 -c "import ast; ast.parse(open('server.py').read()); print('OK')"

# Vérifier les dépendances
python3 -c "import fastmcp, httpx; print('OK')"
```

### Erreur "MOODLE_TOKEN non configuré"

```bash
cat .env  # Vérifier que MOODLE_TOKEN est défini
systemctl restart mcp-moodle
```

### Nginx renvoie 502 Bad Gateway

```bash
# Vérifier que le serveur MCP tourne
systemctl status mcp-moodle
ss -tlnp | grep 8090   # Le port 8090 doit être en écoute
```

### Erreur Moodle "invalidtoken"

- Le token est expiré ou invalide → en générer un nouveau dans Moodle
- L'utilisateur associé au token n'a pas les permissions nécessaires
- Le service web n'a pas les fonctions requises activées

### Certificat SSL introuvable

```bash
ls /etc/letsencrypt/live/   # Vérifier que le certificat existe
certbot certificates         # État de tous les certificats
```

---

## Structure du projet

```
mcp-moodle/
├── server.py              # Serveur MCP principal (115 outils)
├── .env.example           # Template de configuration
├── mcp-moodle.service     # Service systemd
├── nginx-mcp.conf         # Config nginx (template)
├── requirements.txt       # Dépendances Python
└── README.md              # Cette documentation
```

---

## Commandes de gestion

```bash
# Statut
systemctl status mcp-moodle

# Logs en temps réel
journalctl -u mcp-moodle -f

# Redémarrer après modification de server.py ou .env
systemctl restart mcp-moodle

# Arrêter / Démarrer
systemctl stop mcp-moodle
systemctl start mcp-moodle

# Désactiver le démarrage automatique
systemctl disable mcp-moodle
```

---

## Licence

MIT License — Réseaux et Techniques Numériques (RTN)

Développé pour la plateforme e-learning RTN : **https://e-learning.rtn.sn**
