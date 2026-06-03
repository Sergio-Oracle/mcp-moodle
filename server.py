#!/usr/bin/env python3
"""RTN Moodle MCP Server — FastMCP 3.x, transport streamable-http.

Expose https://mcp.rtn.sn/mcp avec 80+ outils couvrant l'API Moodle
de la plateforme e-learning.rtn.sn.
"""

import os
from typing import Optional, Any
import httpx
from fastmcp import FastMCP
from pydantic import Field
from typing import Annotated

MOODLE_URL = os.environ.get("MOODLE_URL", "https://e-learning.rtn.sn").rstrip("/")
MOODLE_TOKEN = os.environ.get("MOODLE_TOKEN", "")
MCP_PORT = int(os.environ.get("MCP_PORT", "8090"))

mcp = FastMCP(
    "RTN Moodle",
    instructions=(
        "Serveur MCP pour la plateforme Moodle RTN (e-learning.rtn.sn). "
        "Permet de gérer cours, utilisateurs, quiz, devoirs, notes, groupes et plus "
        "via l'API Web Service de Moodle. Configurez MOODLE_TOKEN avec votre token."
    ),
)


def _flatten(key: str, value: Any, out: dict) -> None:
    """Recurse nested dict/list → Moodle REST flat key format.
    Moodle attend 0/1 pour les booléens, pas true/false.
    """
    if isinstance(value, list):
        for i, item in enumerate(value):
            if isinstance(item, dict):
                for sub_k, sub_v in item.items():
                    _flatten(f"{key}[{i}][{sub_k}]", sub_v, out)
            elif item is not None:
                out[f"{key}[{i}]"] = 1 if item is True else (0 if item is False else item)
    elif isinstance(value, dict):
        for sub_k, sub_v in value.items():
            _flatten(f"{key}[{sub_k}]", sub_v, out)
    elif value is True:
        out[key] = 1
    elif value is False:
        out[key] = 0
    elif value is not None:
        out[key] = value


async def call_moodle(wsfunction: str, params: dict | None = None) -> Any:
    """POST vers l'API REST Moodle et retourne le JSON."""
    if not MOODLE_TOKEN:
        return {"error": "MOODLE_TOKEN non configuré — définissez la variable d'environnement."}
    api_url = f"{MOODLE_URL}/webservice/rest/server.php"
    data: dict = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
    }
    if params:
        for k, v in params.items():
            if v is not None:
                _flatten(k, v, data)
    async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
        try:
            resp = await client.post(api_url, data=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}", "detail": str(exc)}
        except Exception as exc:
            return {"error": str(exc)}


# ═══════════════════════════ SITE ═══════════════════════════

@mcp.tool()
async def get_site_info() -> dict:
    """Informations du site Moodle et de l'utilisateur connecté (token)."""
    return await call_moodle("core_webservice_get_site_info")


# ═══════════════════════════ UTILISATEURS ═══════════════════════════

@mcp.tool()
async def create_users(
    users: Annotated[list, Field(
        description="Liste d'utilisateurs. Chaque entrée: username, password, firstname, lastname, email, auth(optional)"
    )]
) -> dict:
    """Créer de nouveaux comptes utilisateurs."""
    return await call_moodle("core_user_create_users", {"users": users})


@mcp.tool()
async def get_users(
    criteria: Annotated[list, Field(
        description="Critères. Ex: [{'key':'email','value':'x@y.com'}]. Clés: id, lastname, firstname, idnumber, username, email, auth, confirmed, profile, city, country, firstaccess, lastaccess, lastlogin, timecreated, timemodified, suspended, deleted"
    )]
) -> dict:
    """Rechercher des utilisateurs selon des critères."""
    return await call_moodle("core_user_get_users", {"criteria": criteria})


@mcp.tool()
async def get_users_by_field(
    field: Annotated[str, Field(description="Champ unique: id, idnumber, username, email")],
    values: Annotated[list, Field(description="Valeurs à chercher (liste de chaînes ou d'entiers)")]
) -> dict:
    """Récupérer des utilisateurs par champ unique (id, username, email…)."""
    return await call_moodle("core_user_get_users_by_field", {"field": field, "values": values})


@mcp.tool()
async def update_users(
    users: Annotated[list, Field(description="Utilisateurs à modifier. Chaque entrée doit avoir 'id' + champs à changer.")]
) -> dict:
    """Mettre à jour des utilisateurs existants."""
    return await call_moodle("core_user_update_users", {"users": users})


@mcp.tool()
async def delete_users(
    userids: Annotated[list, Field(description="Liste d'IDs utilisateurs à supprimer")]
) -> dict:
    """Supprimer des utilisateurs."""
    return await call_moodle("core_user_delete_users", {"userids": userids})


@mcp.tool()
async def get_course_user_profiles(
    userlist: Annotated[list, Field(description="Liste d'objets {userid, courseid}")]
) -> dict:
    """Profils utilisateurs dans le contexte d'un cours."""
    return await call_moodle("core_user_get_course_user_profiles", {"userlist": userlist})


@mcp.tool()
async def view_user_list(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Simuler la vue liste des utilisateurs d'un cours (déclenche événements)."""
    return await call_moodle("core_user_view_user_list", {"courseid": courseid})


@mcp.tool()
async def view_user_profile(
    userid: Annotated[int, Field(description="ID de l'utilisateur")],
    courseid: Annotated[Optional[int], Field(description="ID du cours (optionnel)")] = None
) -> dict:
    """Simuler la vue profil d'un utilisateur (déclenche événements)."""
    params: dict = {"userid": userid}
    if courseid:
        params["courseid"] = courseid
    return await call_moodle("core_user_view_user_profile", params)


@mcp.tool()
async def add_user_private_files(
    draftid: Annotated[int, Field(description="itemid de la zone brouillon (draft)")]
) -> dict:
    """Copier des fichiers brouillon vers les fichiers privés de l'utilisateur."""
    return await call_moodle("core_user_add_user_private_files", {"draftid": draftid})


@mcp.tool()
async def confirm_user(
    username: Annotated[str, Field(description="Nom d'utilisateur")],
    secret: Annotated[str, Field(description="Code secret de confirmation")]
) -> dict:
    """Confirmer un compte utilisateur."""
    return await call_moodle("core_auth_confirm_user", {"username": username, "secret": secret})


@mcp.tool()
async def request_password_reset(
    username: Annotated[Optional[str], Field(description="Nom d'utilisateur")] = None,
    email: Annotated[Optional[str], Field(description="Email")] = None
) -> dict:
    """Demander la réinitialisation du mot de passe."""
    params: dict = {}
    if username:
        params["username"] = username
    if email:
        params["email"] = email
    return await call_moodle("core_auth_request_password_reset", params)


# ═══════════════════════════ COURS ═══════════════════════════

@mcp.tool()
async def get_courses(
    ids: Annotated[Optional[list], Field(description="Liste d'IDs de cours (vide = tous)")] = None
) -> dict:
    """Obtenir les détails des cours."""
    params: dict = {}
    if ids:
        params["options"] = {"ids": ids}
    return await call_moodle("core_course_get_courses", params)


@mcp.tool()
async def search_courses(
    criterianame: Annotated[str, Field(description="Critère: search, modulelist, blocklist, tagid")],
    criteriavalue: Annotated[str, Field(description="Valeur du critère")],
    page: Annotated[int, Field(description="Page (0=première)")] = 0,
    perpage: Annotated[int, Field(description="Résultats par page")] = 10
) -> dict:
    """Rechercher des cours par nom, module, bloc ou tag."""
    return await call_moodle("core_course_search_courses", {
        "criterianame": criterianame,
        "criteriavalue": criteriavalue,
        "page": page,
        "perpage": perpage,
    })


@mcp.tool()
async def create_courses(
    courses: Annotated[list, Field(
        description="Cours à créer. Chaque entrée: fullname, shortname, categoryid, format(topics/weeks/social)"
    )]
) -> dict:
    """Créer de nouveaux cours Moodle."""
    return await call_moodle("core_course_create_courses", {"courses": courses})


@mcp.tool()
async def update_courses(
    courses: Annotated[list, Field(description="Cours à modifier. Chaque entrée doit avoir 'id'.")]
) -> dict:
    """Mettre à jour des cours existants."""
    return await call_moodle("core_course_update_courses", {"courses": courses})


@mcp.tool()
async def get_course_contents(
    courseid: Annotated[int, Field(description="ID du cours")],
    options: Annotated[Optional[list], Field(description="Options: [{name,value}]")] = None
) -> dict:
    """Obtenir le contenu d'un cours (sections, modules, ressources)."""
    params: dict = {"courseid": courseid}
    if options:
        params["options"] = options
    return await call_moodle("core_course_get_contents", params)


@mcp.tool()
async def get_categories(
    criteria: Annotated[Optional[list], Field(description="Filtres: [{'key':'id','value':1}]")] = None,
    addsubcategories: Annotated[int, Field(description="1=inclure sous-catégories")] = 1
) -> dict:
    """Obtenir les catégories de cours."""
    params: dict = {"addsubcategories": addsubcategories}
    if criteria:
        params["criteria"] = criteria
    return await call_moodle("core_course_get_categories", params)


@mcp.tool()
async def create_categories(
    categories: Annotated[list, Field(
        description="Catégories à créer: name, parent(0=racine), idnumber, description"
    )]
) -> dict:
    """Créer des catégories de cours."""
    return await call_moodle("core_course_create_categories", {"categories": categories})


@mcp.tool()
async def update_categories(
    categories: Annotated[list, Field(description="Catégories à modifier. Chaque entrée doit avoir 'id'.")]
) -> dict:
    """Mettre à jour des catégories."""
    return await call_moodle("core_course_update_categories", {"categories": categories})


@mcp.tool()
async def delete_categories(
    categories: Annotated[list, Field(description="[{'id':X,'newparent':0,'recursive':0}]")]
) -> dict:
    """Supprimer des catégories de cours."""
    return await call_moodle("core_course_delete_categories", {"categories": categories})


@mcp.tool()
async def get_recent_courses(
    userid: Annotated[Optional[int], Field(description="ID utilisateur (0=courant)")] = 0,
    limit: Annotated[int, Field(description="Nombre max (0=défaut Moodle)")] = 0,
    offset: Annotated[int, Field(description="Décalage pagination")] = 0
) -> dict:
    """Cours récemment accédés par un utilisateur."""
    return await call_moodle("core_course_get_recent_courses", {
        "userid": userid, "limit": limit, "offset": offset
    })


@mcp.tool()
async def get_enrolled_users_by_cmid(
    cmid: Annotated[int, Field(description="ID du module de cours")],
    groupid: Annotated[Optional[int], Field(description="ID du groupe")] = None
) -> dict:
    """Lister les inscrits d'un module de cours."""
    params: dict = {"cmid": cmid}
    if groupid:
        params["groupid"] = groupid
    return await call_moodle("core_course_get_enrolled_users_by_cmid", params)


@mcp.tool()
async def edit_course_module(
    id: Annotated[int, Field(description="ID du module de cours")],
    action: Annotated[str, Field(description="Action: hide, show, stealth, duplicate, delete, indent, outdent, group, ungroup")]
) -> dict:
    """Effectuer une action sur un module de cours."""
    return await call_moodle("core_course_edit_module", {"id": id, "action": action})


@mcp.tool()
async def get_courseformat_file_handlers(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Gestionnaires de fichiers du format de cours actuel."""
    return await call_moodle("core_courseformat_file_handlers", {"courseid": courseid})


# ═══════════════════════════ INSCRIPTIONS ═══════════════════════════

@mcp.tool()
async def get_course_enrolment_methods(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Méthodes d'inscription disponibles pour un cours."""
    return await call_moodle("core_enrol_get_course_enrolment_methods", {"courseid": courseid})


@mcp.tool()
async def get_enrolled_users(
    courseid: Annotated[int, Field(description="ID du cours")],
    options: Annotated[Optional[list], Field(description="Options: [{name,value}]")] = None
) -> dict:
    """Utilisateurs inscrits à un cours."""
    params: dict = {"courseid": courseid}
    if options:
        params["options"] = options
    return await call_moodle("core_enrol_get_enrolled_users", params)


@mcp.tool()
async def get_enrolled_users_with_capability(
    coursecapabilities: Annotated[list, Field(
        description="[{courseid, capabilities:['mod/quiz:manage',...]}]"
    )]
) -> dict:
    """Utilisateurs inscrits possédant une capacité donnée."""
    return await call_moodle(
        "core_enrol_get_enrolled_users_with_capability",
        {"coursecapabilities": coursecapabilities}
    )


@mcp.tool()
async def enrol_users(
    enrolments: Annotated[list, Field(
        description="Inscriptions: [{roleid, userid, courseid, timestart(opt), timeend(opt)}]"
    )]
) -> dict:
    """Inscrire manuellement des utilisateurs à des cours."""
    return await call_moodle("enrol_manual_enrol_users", {"enrolments": enrolments})


@mcp.tool()
async def unenrol_users(
    enrolments: Annotated[list, Field(description="Désinscriptions: [{userid, courseid}]")]
) -> dict:
    """Désinscrire manuellement des utilisateurs de cours."""
    return await call_moodle("enrol_manual_unenrol_users", {"enrolments": enrolments})


# ═══════════════════════════ NOTES / GRADES ═══════════════════════════

@mcp.tool()
async def get_grade_tree(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Structure de l'arbre des notes d'un cours."""
    return await call_moodle("core_grades_get_grade_tree", {"courseid": courseid})


@mcp.tool()
async def update_grades(
    source: Annotated[str, Field(description="Source (ex: 'manual')")],
    courseid: Annotated[int, Field(description="ID du cours")],
    component: Annotated[str, Field(description="Composant (ex: 'mod_assign')")],
    activityid: Annotated[int, Field(description="ID de l'activité")],
    itemnumber: Annotated[int, Field(description="Numéro d'item de note")],
    grades: Annotated[Optional[list], Field(description="[{studentid, grade, str_feedback}]")] = None,
    itemdetails: Annotated[Optional[dict], Field(description="Détails de l'item de note")] = None
) -> dict:
    """Mettre à jour des notes pour une activité."""
    params: dict = {
        "source": source, "courseid": courseid, "component": component,
        "activityid": activityid, "itemnumber": itemnumber,
    }
    if grades:
        params["grades"] = grades
    if itemdetails:
        params["itemdetails"] = itemdetails
    return await call_moodle("core_grades_update_grades", params)


@mcp.tool()
async def get_users_in_grader_report(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Utilisateurs dans le rapport de notes (grader report)."""
    return await call_moodle("gradereport_grader_get_users_in_report", {"courseid": courseid})


@mcp.tool()
async def get_course_grades_overview(
    userid: Annotated[int, Field(description="ID de l'utilisateur (0=utilisateur courant)")] = 0
) -> dict:
    """Notes finales des cours d'un utilisateur (vue d'ensemble)."""
    return await call_moodle("gradereport_overview_get_course_grades", {"userid": userid})


@mcp.tool()
async def get_grade_items_for_user(
    courseid: Annotated[int, Field(description="ID du cours")],
    userid: Annotated[Optional[int], Field(description="ID utilisateur")] = None,
    groupid: Annotated[Optional[int], Field(description="ID groupe")] = None
) -> dict:
    """Liste complète des items de notes pour les utilisateurs d'un cours."""
    params: dict = {"courseid": courseid}
    if userid:
        params["userid"] = userid
    if groupid:
        params["groupid"] = groupid
    return await call_moodle("gradereport_user_get_grade_items", params)


@mcp.tool()
async def get_grades_table(
    courseid: Annotated[int, Field(description="ID du cours")],
    userid: Annotated[Optional[int], Field(description="ID utilisateur")] = None,
    groupid: Annotated[Optional[int], Field(description="ID groupe")] = None
) -> dict:
    """Tableau des notes d'un utilisateur dans un cours."""
    params: dict = {"courseid": courseid}
    if userid:
        params["userid"] = userid
    if groupid:
        params["groupid"] = groupid
    return await call_moodle("gradereport_user_get_grades_table", params)


@mcp.tool()
async def get_grade_items_for_search_widget(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Items de note pour le widget de recherche (singleview report)."""
    return await call_moodle(
        "gradereport_singleview_get_grade_items_for_search_widget", {"courseid": courseid}
    )


@mcp.tool()
async def get_user_grade_report_access(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Informations d'accès au rapport de notes utilisateur."""
    return await call_moodle("gradereport_user_get_access_information", {"courseid": courseid})


@mcp.tool()
async def view_grade_report_overview(
    userid: Annotated[int, Field(description="ID utilisateur")],
    courseid: Annotated[Optional[int], Field(description="ID cours")] = None
) -> dict:
    """Déclencher l'événement vue du rapport global."""
    params: dict = {"userid": userid}
    if courseid:
        params["courseid"] = courseid
    return await call_moodle("gradereport_overview_view_grade_report", params)


@mcp.tool()
async def view_grade_report_user(
    courseid: Annotated[int, Field(description="ID du cours")],
    userid: Annotated[Optional[int], Field(description="ID utilisateur")] = None
) -> dict:
    """Déclencher l'événement vue du rapport de notes utilisateur."""
    params: dict = {"courseid": courseid}
    if userid:
        params["userid"] = userid
    return await call_moodle("gradereport_user_view_grade_report", params)


# ═══════════════════════════ GROUPES ═══════════════════════════

@mcp.tool()
async def create_groups(
    groups: Annotated[list, Field(
        description="Groupes: [{courseid, name, description, enrolmentkey(opt)}]"
    )]
) -> dict:
    """Créer des groupes dans des cours."""
    return await call_moodle("core_group_create_groups", {"groups": groups})


@mcp.tool()
async def add_group_members(
    members: Annotated[list, Field(description="Membres: [{groupid, userid}]")]
) -> dict:
    """Ajouter des membres à des groupes."""
    return await call_moodle("core_group_add_group_members", {"members": members})


@mcp.tool()
async def get_course_groups(
    courseid: Annotated[int, Field(description="ID du cours")]
) -> dict:
    """Tous les groupes d'un cours."""
    return await call_moodle("core_group_get_course_groups", {"courseid": courseid})


# ═══════════════════════════ FICHIERS ═══════════════════════════

@mcp.tool()
async def get_files(
    contextid: Annotated[int, Field(description="ID contexte (mettre -1 pour utiliser contextlevel+instanceid)")],
    component: Annotated[str, Field(description="Composant (ex: 'user', 'course', 'mod_forum')")],
    filearea: Annotated[str, Field(description="Zone (ex: 'private', 'draft', 'attachment')")],
    itemid: Annotated[int, Field(description="ID de l'item (ex: 0 pour fichiers privés)")],
    filepath: Annotated[str, Field(description="Chemin (ex: '/')")] = "/",
    filename: Annotated[str, Field(description="Nom de fichier (vide=répertoire)")] = "",
    contextlevel: Annotated[Optional[str], Field(description="Niveau contexte si contextid=-1 (ex: 'user','course','module')")] = None,
    instanceid: Annotated[Optional[int], Field(description="ID instance si contextid=-1 (ex: userid, courseid)")] = None
) -> dict:
    """Parcourir les fichiers Moodle."""
    params: dict = {
        "contextid": contextid, "component": component, "filearea": filearea,
        "itemid": itemid, "filepath": filepath, "filename": filename,
    }
    if contextlevel:
        params["contextlevel"] = contextlevel
    if instanceid is not None:
        params["instanceid"] = instanceid
    return await call_moodle("core_files_get_files", params)


@mcp.tool()
async def get_unused_draft_itemid() -> dict:
    """Générer un nouvel itemid de brouillon pour l'utilisateur courant."""
    return await call_moodle("core_files_get_unused_draft_itemid")


@mcp.tool()
async def delete_draft_files(
    draftitemid: Annotated[int, Field(description="itemid du brouillon")],
    files: Annotated[list, Field(description="[{filepath, filename}]")]
) -> dict:
    """Supprimer des fichiers d'une zone de brouillon."""
    return await call_moodle("core_files_delete_draft_files", {
        "draftitemid": draftitemid, "files": files
    })


# ═══════════════════════════ CALENDRIER ═══════════════════════════

@mcp.tool()
async def get_calendar_events(
    events: Annotated[Optional[dict], Field(
        description="{eventids:[], courseids:[], groupids:[], categoryids:[]}"
    )] = None,
    options: Annotated[Optional[dict], Field(
        description="{userevents:1, siteevents:1, timestart:0, timeend:0}"
    )] = None
) -> dict:
    """Événements du calendrier."""
    params: dict = {}
    if events:
        params["events"] = events
    if options:
        params["options"] = options
    return await call_moodle("core_calendar_get_calendar_events", params)


@mcp.tool()
async def get_action_events_by_course(
    courseid: Annotated[int, Field(description="ID du cours")],
    timesortfrom: Annotated[Optional[int], Field(description="Timestamp début")] = None,
    timesortto: Annotated[Optional[int], Field(description="Timestamp fin")] = None,
    aftereventid: Annotated[Optional[int], Field(description="Après cet événement")] = None,
    limitnum: Annotated[int, Field(description="Limite d'événements")] = 20
) -> dict:
    """Événements d'action du calendrier pour un cours."""
    params: dict = {"courseid": courseid, "limitnum": limitnum}
    if timesortfrom:
        params["timesortfrom"] = timesortfrom
    if timesortto:
        params["timesortto"] = timesortto
    if aftereventid:
        params["aftereventid"] = aftereventid
    return await call_moodle("core_calendar_get_action_events_by_course", params)


# ═══════════════════════════ COMPÉTENCES ═══════════════════════════

@mcp.tool()
async def create_competency(
    competency: Annotated[dict, Field(
        description="Compétence: {shortname, idnumber, description, competencyframeworkid, parentid}"
    )]
) -> dict:
    """Créer une compétence."""
    return await call_moodle("core_competency_create_competency", {"competency": competency})


@mcp.tool()
async def create_learning_plan(
    plan: Annotated[dict, Field(description="Plan: {userid, name, description, duedate}")]
) -> dict:
    """Créer un plan d'apprentissage."""
    return await call_moodle("core_competency_create_plan", {"plan": plan})


@mcp.tool()
async def complete_learning_plan(
    planid: Annotated[int, Field(description="ID du plan")]
) -> dict:
    """Marquer un plan d'apprentissage comme complété."""
    return await call_moodle("core_competency_complete_plan", {"planid": planid})


@mcp.tool()
async def read_learning_plan(
    id: Annotated[int, Field(description="ID du plan")]
) -> dict:
    """Lire un plan d'apprentissage."""
    return await call_moodle("core_competency_read_plan", {"id": id})


@mcp.tool()
async def list_user_learning_plans(
    userid: Annotated[int, Field(description="ID utilisateur")]
) -> dict:
    """Plans d'apprentissage d'un utilisateur."""
    return await call_moodle("core_competency_list_user_plans", {"userid": userid})


@mcp.tool()
async def create_competency_template(
    shortname: Annotated[str, Field(description="Nom court du template")],
    description: Annotated[str, Field(description="Description")] = "",
    duedate: Annotated[int, Field(description="Timestamp d'échéance (0=aucun)")] = 0,
    visible: Annotated[int, Field(description="1=visible, 0=caché")] = 1,
    contextlevel: Annotated[str, Field(description="Niveau contexte: system, coursecat, course")] = "system",
    instanceid: Annotated[int, Field(description="ID instance (0 pour system)")] = 0
) -> dict:
    """Créer un template de plan d'apprentissage."""
    return await call_moodle("core_competency_create_template", {
        "template": {
            "shortname": shortname, "description": description,
            "duedate": duedate, "visible": visible,
            "contextlevel": contextlevel, "instanceid": instanceid,
        }
    })


@mcp.tool()
async def count_competency_templates(
    contextlevel: Annotated[str, Field(description="Niveau contexte: system, coursecat, course, module, user")] = "system",
    instanceid: Annotated[int, Field(description="ID de l'instance pour le contexte (0 pour system)")] = 0,
    includes: Annotated[str, Field(description="Quels contextes: children, parents, self")] = "children"
) -> dict:
    """Compter les templates de plans d'apprentissage."""
    return await call_moodle("core_competency_count_templates", {
        "context": {"contextlevel": contextlevel, "instanceid": instanceid},
        "includes": includes,
    })


# ═══════════════════════════ COMPLÉTION ═══════════════════════════

@mcp.tool()
async def get_course_completion_status(
    courseid: Annotated[int, Field(description="ID du cours")],
    userid: Annotated[int, Field(description="ID utilisateur")]
) -> dict:
    """Statut de complétion d'un cours pour un utilisateur."""
    return await call_moodle("core_completion_get_course_completion_status", {
        "courseid": courseid, "userid": userid
    })


# ═══════════════════════════ BANQUE DE CONTENU ═══════════════════════════

@mcp.tool()
async def copy_content(
    contentid: Annotated[int, Field(description="ID du contenu à copier")],
    name: Annotated[str, Field(description="Nouveau nom pour la copie")]
) -> dict:
    """Copier un contenu dans la banque de contenu (Moodle 4.3+)."""
    return await call_moodle("core_contentbank_copy_content", {
        "contentid": contentid, "name": name
    })


# ═══════════════════════════ CHAMPS PERSONNALISÉS ═══════════════════════════

@mcp.tool()
async def create_custom_field_category(
    component: Annotated[str, Field(description="Composant (ex: 'core_course', 'mod_quiz')")],
    area: Annotated[str, Field(description="Zone (ex: 'course', 'quiz')")],
    itemid: Annotated[int, Field(description="ID de l'item (0 pour global)")] = 0
) -> dict:
    """Créer une catégorie de champ personnalisé. Retourne l'ID de la catégorie créée."""
    return await call_moodle("core_customfield_create_category", {
        "component": component, "area": area, "itemid": itemid
    })


# ═══════════════════════════ NOTES (ANNOTATIONS) ═══════════════════════════

@mcp.tool()
async def create_notes(
    notes: Annotated[list, Field(
        description="[{userid, publishstate(personal/draft/site), courseid, text, format(1=HTML)}]"
    )]
) -> dict:
    """Créer des annotations sur des utilisateurs."""
    return await call_moodle("core_notes_create_notes", {"notes": notes})


@mcp.tool()
async def get_course_notes(
    courseid: Annotated[int, Field(description="ID du cours")],
    userid: Annotated[int, Field(description="ID utilisateur (0=tous)")] = 0
) -> dict:
    """Notes d'un cours pour un utilisateur."""
    return await call_moodle("core_notes_get_course_notes", {
        "courseid": courseid, "userid": userid
    })


# ═══════════════════════════ MESSAGERIE ═══════════════════════════

@mcp.tool()
async def get_blocked_users(
    userid: Annotated[int, Field(description="ID utilisateur")]
) -> dict:
    """Utilisateurs bloqués par un utilisateur."""
    return await call_moodle("core_message_get_blocked_users", {"userid": userid})


# ═══════════════════════════ QUESTIONS ═══════════════════════════

@mcp.tool()
async def get_random_question_summaries(
    categoryid: Annotated[int, Field(description="ID catégorie de questions")],
    includesubcategories: Annotated[bool, Field(description="Inclure sous-catégories")],
    tagids: Annotated[list, Field(description="IDs de tags (liste vide [] si aucun filtre)")],
    contextid: Annotated[int, Field(description="ID contexte pour le rendu des questions")],
    limit: Annotated[int, Field(description="Limite (0=par défaut)")] = 0,
    offset: Annotated[int, Field(description="Décalage")] = 0
) -> dict:
    """Ensemble de questions aléatoires selon des critères."""
    return await call_moodle("core_question_get_random_question_summaries", {
        "categoryid": categoryid,
        "includesubcategories": includesubcategories,
        "tagids": tagids,
        "contextid": contextid,
        "limit": limit,
        "offset": offset,
    })


@mcp.tool()
async def update_question_flag(
    qubaid: Annotated[int, Field(description="ID usage banque questions")],
    questionid: Annotated[int, Field(description="ID question")],
    qaid: Annotated[int, Field(description="ID question attempt")],
    slot: Annotated[int, Field(description="Slot")],
    checksum: Annotated[str, Field(description="Checksum MD5(qubaid+questionid+qaid+username) — calculé côté client")],
    newstate: Annotated[bool, Field(description="True=flaggée, False=non flaggée")]
) -> dict:
    """Mettre à jour le flag d'une question (nécessite un checksum de sécurité)."""
    return await call_moodle("core_question_update_flag", {
        "qubaid": qubaid, "questionid": questionid,
        "qaid": qaid, "slot": slot, "checksum": checksum, "newstate": newstate,
    })


# ═══════════════════════════ QUIZ LOCAL_MCP (PLUGIN PERSONNALISÉ RTN) ═══════════════════════════

@mcp.tool()
async def mcp_create_quiz(
    courseid: Annotated[int, Field(description="ID du cours")],
    name: Annotated[str, Field(description="Nom du quiz")],
    intro: Annotated[str, Field(description="Introduction/description")] = "",
    timeopen: Annotated[int, Field(description="Timestamp ouverture (0=sans)")] = 0,
    timeclose: Annotated[int, Field(description="Timestamp fermeture (0=sans)")] = 0,
    timelimit: Annotated[int, Field(description="Limite temps secondes (0=illimité)")] = 0,
    attempts: Annotated[int, Field(description="Tentatives max (0=illimité)")] = 0,
    grademethod: Annotated[int, Field(description="1=meilleure, 2=dernière, 3=moyenne, 4=première")] = 1
) -> dict:
    """Créer un quiz (via plugin local_mcp RTN)."""
    return await call_moodle("local_mcp_quiz_créer_quiz", {
        "courseid": courseid, "name": name, "intro": intro,
        "timeopen": timeopen, "timeclose": timeclose, "timelimit": timelimit,
        "attempts": attempts, "grademethod": grademethod,
    })


@mcp.tool()
async def mcp_create_question_category(
    contextid: Annotated[int, Field(description="ID contexte (module ou cours)")],
    name: Annotated[str, Field(description="Nom de la catégorie")],
    info: Annotated[str, Field(description="Description")] = "",
    parent: Annotated[int, Field(description="ID catégorie parente (0=racine)")] = 0
) -> dict:
    """Créer une catégorie de questions (via plugin local_mcp RTN)."""
    return await call_moodle("catégorie_de_question_créer_quiz_local_mcp", {
        "contextid": contextid, "name": name, "info": info, "parent": parent,
    })


@mcp.tool()
async def mcp_add_question_to_quiz(
    quizid: Annotated[int, Field(description="ID du quiz")],
    questionid: Annotated[int, Field(description="ID de la question")],
    page: Annotated[int, Field(description="Page dans le quiz (0=dernière)")] = 0
) -> dict:
    """Ajouter une question à un quiz (via plugin local_mcp RTN)."""
    return await call_moodle("local_mcp_quiz_ajouter_question_au_quiz", {
        "quizid": quizid, "questionid": questionid, "page": page,
    })


@mcp.tool()
async def mcp_create_multichoice_question(
    categoryid: Annotated[int, Field(description="ID catégorie de questions")],
    name: Annotated[str, Field(description="Nom de la question")],
    questiontext: Annotated[str, Field(description="Texte de la question (HTML)")],
    answers: Annotated[list, Field(
        description="[{text, fraction(0-1), feedback(optionnel)}]. fraction=1 pour correcte."
    )]
) -> dict:
    """Créer une question à choix multiple (via plugin local_mcp RTN). La note, le type choix unique/multiple et le mélange sont gérés automatiquement par le plugin."""
    return await call_moodle("local_mcp_quiz_create_multichoice_question", {
        "categoryid": categoryid, "name": name, "questiontext": questiontext,
        "answers": answers,
    })


@mcp.tool()
async def mcp_create_shortanswer_question(
    categoryid: Annotated[int, Field(description="ID catégorie")],
    name: Annotated[str, Field(description="Nom de la question")],
    questiontext: Annotated[str, Field(description="Texte (HTML)")],
    answers: Annotated[list, Field(description="[{text, fraction(0-1)}] — PAS de champ feedback")]
) -> dict:
    """Créer une question à réponse courte (via plugin local_mcp RTN). Note par défaut=1, casse insensible."""
    return await call_moodle("local_mcp_quiz_create_shortanswer_question", {
        "categoryid": categoryid, "name": name, "questiontext": questiontext,
        "answers": answers,
    })


@mcp.tool()
async def mcp_create_truefalse_question(
    categoryid: Annotated[int, Field(description="ID catégorie")],
    name: Annotated[str, Field(description="Nom de la question")],
    questiontext: Annotated[str, Field(description="Texte (HTML)")],
    correctanswer: Annotated[int, Field(description="Réponse correcte: 1=Vrai, 0=Faux")]
) -> dict:
    """Créer une question Vrai/Faux (via plugin local_mcp RTN). Note=1, feedbacks gérés automatiquement."""
    return await call_moodle("local_mcp_quiz_create_truefalse_question", {
        "categoryid": categoryid, "name": name, "questiontext": questiontext,
        "correctanswer": correctanswer,
    })


# ═══════════════════════════ FORUM ═══════════════════════════

@mcp.tool()
async def get_forums_by_courses(
    courseids: Annotated[list, Field(description="IDs de cours")]
) -> dict:
    """Forums d'une liste de cours."""
    return await call_moodle("mod_forum_get_forums_by_courses", {"courseids": courseids})


@mcp.tool()
async def get_forum_discussions(
    forumid: Annotated[int, Field(description="ID du forum")],
    sortorder: Annotated[int, Field(description="Tri: -1=défaut, 1=numreplies, 2=created, 3=timemodified")] = -1,
    page: Annotated[int, Field(description="Page (-1=toutes)")] = -1,
    perpage: Annotated[int, Field(description="Par page (0=défaut)")] = 0,
    groupid: Annotated[int, Field(description="Groupe (0=tous)")] = 0
) -> dict:
    """Discussions d'un forum."""
    return await call_moodle("mod_forum_get_forum_discussions", {
        "forumid": forumid, "sortorder": sortorder,
        "page": page, "perpage": perpage, "groupid": groupid,
    })


@mcp.tool()
async def add_forum_discussion(
    forumid: Annotated[int, Field(description="ID du forum")],
    subject: Annotated[str, Field(description="Sujet")],
    message: Annotated[str, Field(description="Message (HTML uniquement)")],
    groupid: Annotated[int, Field(description="Groupe (0=tous)")] = 0,
    options: Annotated[Optional[list], Field(description="[{name,value}] — ex: [{name:'discussionsubscribe',value:'1'}]")] = None
) -> dict:
    """Créer une nouvelle discussion dans un forum."""
    params: dict = {"forumid": forumid, "subject": subject, "message": message, "groupid": groupid}
    if options:
        params["options"] = options
    return await call_moodle("mod_forum_add_discussion", params)


@mcp.tool()
async def add_forum_discussion_post(
    postid: Annotated[int, Field(description="ID du post parent")],
    subject: Annotated[str, Field(description="Sujet")],
    message: Annotated[str, Field(description="Message HTML")],
    messageformat: Annotated[int, Field(description="1=HTML, 2=plain, 4=markdown")] = 1,
    options: Annotated[Optional[list], Field(description="[{name,value}]")] = None
) -> dict:
    """Répondre dans une discussion de forum."""
    params: dict = {
        "postid": postid, "subject": subject, "message": message,
        "messageformat": messageformat,
    }
    if options:
        params["options"] = options
    return await call_moodle("mod_forum_add_discussion_post", params)


# ═══════════════════════════ DEVOIRS (ASSIGN) ═══════════════════════════

@mcp.tool()
async def get_assignments(
    courseids: Annotated[Optional[list], Field(description="IDs cours (vide=tous)")] = None,
    capabilities: Annotated[Optional[list], Field(description="Capacités requises")] = None
) -> dict:
    """Devoirs des cours accessibles à l'utilisateur."""
    params: dict = {}
    if courseids:
        params["courseids"] = courseids
    if capabilities:
        params["capabilities"] = capabilities
    return await call_moodle("mod_assign_get_assignments", params)


@mcp.tool()
async def get_assignment_submissions(
    assignmentids: Annotated[list, Field(description="IDs de devoirs")],
    status: Annotated[str, Field(description="Filtre: '' / new / draft / submitted / reopened")] = "",
    since: Annotated[int, Field(description="Timestamp min")] = 0,
    before: Annotated[int, Field(description="Timestamp max")] = 0
) -> dict:
    """Soumissions de devoirs."""
    return await call_moodle("mod_assign_get_submissions", {
        "assignmentids": assignmentids, "status": status,
        "since": since, "before": before,
    })


@mcp.tool()
async def get_assignment_submission_status(
    assignid: Annotated[int, Field(description="ID du devoir")],
    userid: Annotated[Optional[int], Field(description="ID utilisateur")] = None,
    groupid: Annotated[Optional[int], Field(description="ID groupe")] = None
) -> dict:
    """Statut de soumission d'un devoir pour un utilisateur."""
    params: dict = {"assignid": assignid}
    if userid:
        params["userid"] = userid
    if groupid:
        params["groupid"] = groupid
    return await call_moodle("mod_assign_get_submission_status", params)


@mcp.tool()
async def get_assignment_grades(
    assignmentids: Annotated[list, Field(description="IDs de devoirs")],
    since: Annotated[int, Field(description="Timestamp min")] = 0
) -> dict:
    """Notes de devoirs."""
    return await call_moodle("mod_assign_get_grades", {
        "assignmentids": assignmentids, "since": since
    })


@mcp.tool()
async def save_assignment_grade(
    assignmentid: Annotated[int, Field(description="ID du devoir")],
    userid: Annotated[int, Field(description="ID étudiant")],
    grade: Annotated[float, Field(description="Note (-1=pas de note)")],
    attemptnumber: Annotated[int, Field(description="Numéro tentative (-1=dernière)")] = -1,
    addattempt: Annotated[int, Field(description="Ajouter tentative (1=oui)")] = 0,
    workflowstate: Annotated[str, Field(description="État workflow: '' / released / notgraded / inreview / readyforrelease / inmarking")] = "",
    applytoall: Annotated[int, Field(description="Appliquer à tout le groupe (1=oui)")] = 0
) -> dict:
    """Sauvegarder une note pour un étudiant dans un devoir."""
    return await call_moodle("mod_assign_save_grade", {
        "assignmentid": assignmentid, "userid": userid, "grade": grade,
        "attemptnumber": attemptnumber, "addattempt": addattempt,
        "workflowstate": workflowstate, "applytoall": applytoall,
    })


@mcp.tool()
async def list_assignment_participants(
    assignid: Annotated[int, Field(description="ID du devoir")],
    groupid: Annotated[int, Field(description="Groupe (0=tous)")] = 0,
    filter: Annotated[str, Field(description="Filtre texte")] = "",
    skip: Annotated[int, Field(description="À ignorer")] = 0,
    limit: Annotated[int, Field(description="Max (0=tous)")] = 0,
    onlyids: Annotated[bool, Field(description="Seulement les IDs")] = False,
    includeenrolments: Annotated[bool, Field(description="Inclure infos inscription")] = True
) -> dict:
    """Participants à un devoir."""
    return await call_moodle("mod_assign_list_participants", {
        "assignid": assignid, "groupid": groupid, "filter": filter,
        "skip": skip, "limit": limit,
        "onlyids": 1 if onlyids else 0,
        "includeenrolments": 1 if includeenrolments else 0,
    })


# ═══════════════════════════ QUIZ MOD ═══════════════════════════

@mcp.tool()
async def get_quizzes_by_courses(
    courseids: Annotated[list, Field(description="IDs cours (vide=tous)")]
) -> dict:
    """Liste des quiz dans des cours."""
    return await call_moodle("mod_quiz_get_quizzes_by_courses", {"courseids": courseids})


@mcp.tool()
async def get_quiz_access_information(
    quizid: Annotated[int, Field(description="ID du quiz")]
) -> dict:
    """Informations d'accès à un quiz."""
    return await call_moodle("mod_quiz_get_quiz_access_information", {"quizid": quizid})


@mcp.tool()
async def start_quiz_attempt(
    quizid: Annotated[int, Field(description="ID du quiz")],
    preflightdata: Annotated[Optional[list], Field(description="[{name,value}]")] = None,
    forcenew: Annotated[bool, Field(description="Forcer nouvelle tentative")] = False
) -> dict:
    """Démarrer une tentative de quiz."""
    params: dict = {"quizid": quizid, "forcenew": 1 if forcenew else 0}
    if preflightdata:
        params["preflightdata"] = preflightdata
    return await call_moodle("mod_quiz_start_attempt", params)


@mcp.tool()
async def get_quiz_attempt_data(
    attemptid: Annotated[int, Field(description="ID tentative")],
    page: Annotated[int, Field(description="Numéro de page")],
    preflightdata: Annotated[Optional[list], Field(description="[{name,value}]")] = None
) -> dict:
    """Données d'une page de tentative de quiz."""
    params: dict = {"attemptid": attemptid, "page": page}
    if preflightdata:
        params["preflightdata"] = preflightdata
    return await call_moodle("mod_quiz_get_attempt_data", params)


@mcp.tool()
async def save_quiz_attempt(
    attemptid: Annotated[int, Field(description="ID tentative")],
    data: Annotated[list, Field(description="[{name,value}]")]
) -> dict:
    """Auto-sauvegarder une tentative de quiz."""
    return await call_moodle("mod_quiz_save_attempt", {"attemptid": attemptid, "data": data})


@mcp.tool()
async def process_quiz_attempt(
    attemptid: Annotated[int, Field(description="ID tentative")],
    data: Annotated[list, Field(description="Réponses: [{name,value}]")],
    finishattempt: Annotated[bool, Field(description="Terminer la tentative")] = False,
    timeup: Annotated[bool, Field(description="Temps écoulé")] = False,
    preflightdata: Annotated[Optional[list], Field(description="[{name,value}]")] = None
) -> dict:
    """Traiter les réponses et/ou terminer une tentative de quiz."""
    params: dict = {
        "attemptid": attemptid, "data": data,
        "finishattempt": 1 if finishattempt else 0,
        "timeup": 1 if timeup else 0,
    }
    if preflightdata:
        params["preflightdata"] = preflightdata
    return await call_moodle("mod_quiz_process_attempt", params)


@mcp.tool()
async def get_quiz_attempt_summary(
    attemptid: Annotated[int, Field(description="ID tentative")],
    preflightdata: Annotated[Optional[list], Field(description="[{name,value}]")] = None
) -> dict:
    """Résumé d'une tentative de quiz avant soumission finale."""
    params: dict = {"attemptid": attemptid}
    if preflightdata:
        params["preflightdata"] = preflightdata
    return await call_moodle("mod_quiz_get_attempt_summary", params)


@mcp.tool()
async def get_quiz_attempt_review(
    attemptid: Annotated[int, Field(description="ID tentative")],
    page: Annotated[int, Field(description="Page (-1=toutes)")] = -1
) -> dict:
    """Révision d'une tentative terminée."""
    return await call_moodle("mod_quiz_get_attempt_review", {"attemptid": attemptid, "page": page})


@mcp.tool()
async def get_quiz_attempt_access_information(
    quizid: Annotated[int, Field(description="ID du quiz")],
    attemptid: Annotated[int, Field(description="ID tentative (0=aucune)")] = 0
) -> dict:
    """Informations d'accès pour une tentative de quiz."""
    return await call_moodle("mod_quiz_get_attempt_access_information", {
        "quizid": quizid, "attemptid": attemptid
    })


@mcp.tool()
async def get_user_quiz_attempts(
    quizid: Annotated[int, Field(description="ID du quiz")],
    userid: Annotated[int, Field(description="ID utilisateur (0=courant)")] = 0,
    status: Annotated[str, Field(description="all / finished / unfinished")] = "all",
    includepreviews: Annotated[bool, Field(description="Inclure aperçus")] = False
) -> dict:
    """Tentatives d'un utilisateur pour un quiz."""
    return await call_moodle("mod_quiz_get_user_attempts", {
        "quizid": quizid, "userid": userid, "status": status,
        "includepreviews": 1 if includepreviews else 0,
    })


@mcp.tool()
async def get_user_best_quiz_grade(
    quizid: Annotated[int, Field(description="ID du quiz")],
    userid: Annotated[int, Field(description="ID utilisateur (0=courant)")] = 0
) -> dict:
    """Meilleure note d'un utilisateur dans un quiz."""
    return await call_moodle("mod_quiz_get_user_best_grade", {"quizid": quizid, "userid": userid})


@mcp.tool()
async def get_quiz_combined_review_options(
    quizid: Annotated[int, Field(description="ID du quiz")],
    userid: Annotated[int, Field(description="ID utilisateur (0=courant)")] = 0
) -> dict:
    """Options de révision combinées pour un quiz."""
    return await call_moodle("mod_quiz_get_combined_review_options", {
        "quizid": quizid, "userid": userid
    })


@mcp.tool()
async def get_quiz_feedback_for_grade(
    quizid: Annotated[int, Field(description="ID du quiz")],
    grade: Annotated[float, Field(description="Note obtenue")]
) -> dict:
    """Feedback associé à une note dans un quiz."""
    return await call_moodle("mod_quiz_get_quiz_feedback_for_grade", {"quizid": quizid, "grade": grade})


@mcp.tool()
async def get_quiz_required_qtypes(
    quizid: Annotated[int, Field(description="ID du quiz")]
) -> dict:
    """Types de questions requis pour un quiz."""
    return await call_moodle("mod_quiz_get_quiz_required_qtypes", {"quizid": quizid})


@mcp.tool()
async def view_quiz(quizid: Annotated[int, Field(description="ID du quiz")]) -> dict:
    """Déclencher l'événement de vue d'un quiz."""
    return await call_moodle("mod_quiz_view_quiz", {"quizid": quizid})


@mcp.tool()
async def view_quiz_attempt(
    attemptid: Annotated[int, Field(description="ID tentative")],
    page: Annotated[int, Field(description="Numéro de page")]
) -> dict:
    """Déclencher l'événement de vue d'une tentative."""
    return await call_moodle("mod_quiz_view_attempt", {"attemptid": attemptid, "page": page})


@mcp.tool()
async def view_quiz_attempt_summary(
    attemptid: Annotated[int, Field(description="ID tentative")]
) -> dict:
    """Déclencher l'événement vue résumé tentative."""
    return await call_moodle("mod_quiz_view_attempt_summary", {"attemptid": attemptid})


@mcp.tool()
async def view_quiz_attempt_review(
    attemptid: Annotated[int, Field(description="ID tentative")]
) -> dict:
    """Déclencher l'événement révision tentative."""
    return await call_moodle("mod_quiz_view_attempt_review", {"attemptid": attemptid})


@mcp.tool()
async def add_random_questions_to_quiz(
    cmid: Annotated[int, Field(description="ID du module de cours (cmid) du quiz")],
    addonpage: Annotated[int, Field(description="Page cible dans le quiz")],
    randomcount: Annotated[int, Field(description="Nombre de questions aléatoires à ajouter")],
    filtercondition: Annotated[str, Field(description="Condition de filtre JSON (catégorie existante). Ex: '{\"filter\":{\"category\":{\"id\":4}}}'")] = "",
    newcategory: Annotated[str, Field(description="Nom d'une nouvelle catégorie à créer (optionnel)")] = "",
    parentcategory: Annotated[str, Field(description="Catégorie parente si newcategory défini")] = ""
) -> dict:
    """Ajouter des questions aléatoires à un quiz (utilise le cmid, pas le quizid)."""
    return await call_moodle("mod_quiz_add_random_questions", {
        "cmid": cmid, "addonpage": addonpage, "randomcount": randomcount,
        "filtercondition": filtercondition, "newcategory": newcategory,
        "parentcategory": parentcategory,
    })


@mcp.tool()
async def create_quiz_grade_items(
    quizid: Annotated[int, Field(description="ID du quiz")],
    quizgradeitems: Annotated[list, Field(description="[{name}] — nom de chaque item de note à créer")]
) -> dict:
    """Créer des items de note pour un quiz."""
    return await call_moodle("mod_quiz_create_grade_items", {"quizid": quizid, "quizgradeitems": quizgradeitems})


@mcp.tool()
async def create_quiz_grade_item_per_section(
    quizid: Annotated[int, Field(description="ID du quiz")]
) -> dict:
    """Créer un item de note par section de quiz."""
    return await call_moodle("mod_quiz_create_grade_item_per_section", {"quizid": quizid})


@mcp.tool()
async def update_quiz_grade_items(
    quizid: Annotated[int, Field(description="ID du quiz")],
    quizgradeitems: Annotated[list, Field(description="[{id, name(opt)}] — id requis")]
) -> dict:
    """Mettre à jour les items de note d'un quiz."""
    return await call_moodle("mod_quiz_update_grade_items", {"quizid": quizid, "quizgradeitems": quizgradeitems})


@mcp.tool()
async def delete_quiz_grade_items(
    quizid: Annotated[int, Field(description="ID du quiz")],
    quizgradeitems: Annotated[list, Field(description="[{id}] — IDs des items de note à supprimer")]
) -> dict:
    """Supprimer des items de note d'un quiz."""
    return await call_moodle("mod_quiz_delete_grade_items", {"quizid": quizid, "quizgradeitems": quizgradeitems})


@mcp.tool()
async def get_quiz_overrides(
    quizid: Annotated[int, Field(description="ID du quiz")]
) -> dict:
    """Exceptions d'un quiz (overrides) — retourne toutes les exceptions."""
    return await call_moodle("mod_quiz_get_overrides", {"quizid": quizid})


@mcp.tool()
async def save_quiz_overrides(
    quizid: Annotated[int, Field(description="ID du quiz")],
    overrides: Annotated[list, Field(
        description="[{userid(opt), groupid(opt), timeopen(opt), timeclose(opt), timelimit(opt), attempts(opt), password(opt)}]"
    )]
) -> dict:
    """Sauvegarder des exceptions pour un quiz."""
    return await call_moodle("mod_quiz_save_overrides", {
        "data": {"quizid": quizid, "overrides": overrides}
    })


@mcp.tool()
async def delete_quiz_overrides(
    quizid: Annotated[int, Field(description="ID du quiz")],
    ids: Annotated[list, Field(description="Liste d'IDs d'exceptions à supprimer (ex: [1, 2, 3])")]
) -> dict:
    """Supprimer des exceptions d'un quiz."""
    return await call_moodle("mod_quiz_delete_overrides", {
        "data": {"quizid": quizid, "ids": ids}
    })


@mcp.tool()
async def get_reopen_attempt_confirmation(
    attemptid: Annotated[int, Field(description="ID de la tentative à rouvrir")]
) -> dict:
    """Vérifier si la réouverture d'une tentative abandonée est possible (retourne message de confirmation)."""
    return await call_moodle("mod_quiz_get_reopen_attempt_confirmation", {"attemptid": attemptid})


@mcp.tool()
async def reopen_quiz_attempt(
    attemptid: Annotated[int, Field(description="ID de la tentative à rouvrir (doit être en état 'abandoned')")]
) -> dict:
    """Rouvrir une tentative de quiz en état 'abandoned'."""
    return await call_moodle("mod_quiz_reopen_attempt", {"attemptid": attemptid})


@mcp.tool()
async def update_quiz_slots(
    quizid: Annotated[int, Field(description="ID du quiz")],
    slots: Annotated[list, Field(description="[{id, displaynumber(opt), requireprevious(opt), maxmark(opt), quizgradeitemid(opt)}]")]
) -> dict:
    """Mettre à jour les propriétés des slots d'un quiz."""
    return await call_moodle("mod_quiz_update_slots", {"quizid": quizid, "slots": slots})


@mcp.tool()
async def update_quiz_filter_condition(
    cmid: Annotated[int, Field(description="ID du module de cours (cmid) du quiz")],
    slotid: Annotated[int, Field(description="ID du slot de question aléatoire")],
    filtercondition: Annotated[str, Field(description="Condition de filtre JSON")]
) -> dict:
    """Mettre à jour la condition de filtre d'un slot question aléatoire (utilise cmid, pas quizid)."""
    return await call_moodle("mod_quiz_update_filter_condition", {
        "cmid": cmid, "slotid": slotid, "filtercondition": filtercondition
    })


@mcp.tool()
async def set_quiz_question_version(
    slotid: Annotated[int, Field(description="ID du slot")],
    newversion: Annotated[int, Field(description="Version (-1=toujours la dernière)")]
) -> dict:
    """Définir la version d'une question dans un slot de quiz."""
    return await call_moodle("mod_quiz_set_question_version", {
        "slotid": slotid, "newversion": newversion
    })


@mcp.tool()
async def get_quiz_edit_grading_page(
    quizid: Annotated[int, Field(description="ID du quiz")]
) -> dict:
    """Données pour la page de configuration de notation du quiz."""
    return await call_moodle("mod_quiz_get_edit_grading_page_data", {"quizid": quizid})


# ═══════════════════════════ RESSOURCES ═══════════════════════════

@mcp.tool()
async def get_resources_by_courses(
    courseids: Annotated[Optional[list], Field(description="IDs cours (vide=tous)")] = None
) -> dict:
    """Ressources (fichiers) dans des cours."""
    params: dict = {}
    if courseids:
        params["courseids"] = courseids
    return await call_moodle("mod_resource_get_resources_by_courses", params)


# ═══════════════════════════ ÉLÉMENTS RÉCENTS ═══════════════════════════

@mcp.tool()
async def get_recent_items(
    limit: Annotated[int, Field(description="Nombre max d'éléments (0=défaut Moodle)")] = 0
) -> dict:
    """Éléments récemment accédés par l'utilisateur courant du token."""
    return await call_moodle("block_recentlyaccesseditems_get_recent_items", {"limit": limit})


# ═══════════════════════════ MOODLENET ═══════════════════════════

@mcp.tool()
async def send_activity_to_moodlenet(
    issuerid: Annotated[int, Field(description="ID de l'émetteur OAuth2 MoodleNet configuré")],
    cmid: Annotated[int, Field(description="ID du module de cours à partager")],
    shareformat: Annotated[int, Field(description="Format de partage (1=backup)")] = 1
) -> dict:
    """Partager une activité vers MoodleNet (requiert un OAuth2 issuer MoodleNet configuré)."""
    return await call_moodle("core_moodlenet_send_activity", {
        "issuerid": issuerid, "cmid": cmid, "shareformat": shareformat
    })


# ═══════════════════════════ xAPI ═══════════════════════════

@mcp.tool()
async def delete_xapi_state(
    component: Annotated[str, Field(description="Composant (ex: 'mod_h5pactivity')")],
    activityId: Annotated[str, Field(description="IRI de l'activité xAPI (URL)")],
    agent: Annotated[str, Field(description="Agent xAPI JSON stringifié")],
    stateId: Annotated[str, Field(description="ID de l'état xAPI")],
    registration: Annotated[Optional[str], Field(description="UUID d'enregistrement (optionnel)")] = None
) -> dict:
    """Supprimer un état xAPI d'une activité. stateId = lettres/tirets/underscores uniquement (ALPHAEXT, pas de chiffres)."""
    params: dict = {
        "component": component, "activityId": activityId,
        "agent": agent, "stateId": stateId,
    }
    if registration:
        params["registration"] = registration
    return await call_moodle("core_xapi_delete_state", params)


# ═══════════════════════════ DÉMARRAGE ═══════════════════════════

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=MCP_PORT,
        path="/mcp",
        log_level="info",
    )
