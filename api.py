from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException
from datetime import datetime
from dotenv import load_dotenv
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from functools import wraps
from flask_wtf.csrf import CSRFProtect, generate_csrf
import sqlite3
import time
import json
import uuid
import os
import database


load_dotenv()
ph = PasswordHasher()
app = Flask(__name__, static_folder="web", static_url_path="")
app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost"]
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
# Sécurisation des cookies de session
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "Data_base.db")
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("La variable SECRET_KEY est absente du fichier .env")
csrf = CSRFProtect(app)


#Couleur de mes themes 
list_color = [
    "violet",
    "red",
    "green",
    "blue",
    "ocre",
    "petrole"
]


# Limites de saisie
TAILLE_MAX_LIST_NAME = 50
TAILLE_MAX_TASK_TITLE = 70
TAILLE_MAX_STEP_TITLE = 100
TAILLE_MAX_NOTE = 500
NOMBRE_MAX_STEPS = 20
TAILLE_MAX_USERNAME = 50
TAILLE_MIN_PASSWORD = 8
TAILLE_MAX_PASSWORD = 128


# Connexion commune à la base de données
def get_db_connection():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


# Vérifier que l'utilisateur est connecté
def login_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:
            return jsonify({"error": "Authentification requise"}), 401

        return view(*args, **kwargs)

    return wrapped_view


# Récupération du jeton CSRF
@app.route("/api/v1/auth/csrf", methods=["GET"])
def get_csrf_token():
    return jsonify({"csrf_token": generate_csrf()})


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/", methods=["GET"])
def index():
    return send_from_directory("web", "index.html")


# Récupérer les listes
@app.route("/api/v1/lists", methods=["GET"])
@login_required
def get_lists():

    con = get_db_connection()
    cur = con.cursor()

    try:
        user_id = session["user_id"]

        cur.execute(
            "SELECT id, name, theme FROM list WHERE is_deleted = 0 AND user_id = ?",
            (user_id,)
        )

        lists = [dict(row) for row in cur.fetchall()]

        return jsonify(lists)

    finally:
        con.close()


# Créer une liste
@app.route("/api/v1/lists", methods=["POST"])
@login_required
def create_list():
    data = request.get_json(silent=True)
    user_id = session["user_id"]

    if not isinstance(data, dict):
        return jsonify("error"), 400

    name = data.get("name")
    theme = data.get("theme")

    if not isinstance(name, str) or not name.strip():
        return jsonify("error"), 400

    name = name.strip()

    if len(name) > TAILLE_MAX_LIST_NAME:
        return jsonify("error"), 400

    if not isinstance(theme, str) or theme not in list_color:
        return jsonify("error"), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO list (name, theme, user_id)
            VALUES (?, ?, ?)
            """,
            (name, theme, user_id)
        )

        list_id = cur.lastrowid
        con.commit()

        return jsonify({
            "id": list_id,
            "message": "Liste créée"
        }), 201

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Créer une tâche
@app.route("/api/v1/tasks", methods=["POST"])
@login_required
def creat_task():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify("error"), 400

    title = data.get("title")

    if not isinstance(title, str) or not title.strip():
        return jsonify("error"), 400

    title = title.strip()

    if len(title) > TAILLE_MAX_TASK_TITLE:
        return jsonify("error"), 400

    list_id = data.get("listId")
    my_day = data.get("myDay", False)
    important = data.get("important", False)
    due = data.get("due")

    if isinstance(list_id, bool) or (
        list_id is not None and not isinstance(list_id, int)
    ):
        return jsonify("error"), 400

    if not isinstance(my_day, bool):
        return jsonify("error"), 400

    if not isinstance(important, bool):
        return jsonify("error"), 400

    if due is not None and not isinstance(due, str):
        return jsonify("error"), 400

    
    if due is not None and (not isinstance(due, str) or len(due) != 10):
        return jsonify("error"), 400

    if due is not None:
        try:
            datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            return jsonify("error"), 400

    con = get_db_connection()

    created_at = int(time.time() * 1000)

    try:
        cur = con.cursor()
        user_id = session["user_id"] 

        if list_id is not None:
            cur.execute(
                "SELECT id, is_deleted FROM list WHERE id = ? AND user_id = ?",
                (list_id, user_id) 
            )

            destination_list = cur.fetchone()

            if destination_list is None:
                return jsonify("error"), 404

            if destination_list["is_deleted"] == 1:
                return jsonify("error"), 404
        cur.execute(
            """
            INSERT INTO task
                (title, done, important, myDay, due, listId, createdAt, user_id)
            VALUES (?, 0, ?, ?, ?, ?, ?, ?)
            """,
            (title, important, my_day, due, list_id, created_at, user_id)
        )

        task_id = cur.lastrowid
        con.commit()

        return jsonify({
            "id": task_id,
            "message": "Tâche enregistrée"
        }), 201

    except sqlite3.IntegrityError:
        con.rollback()
        return jsonify("error"), 400

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Récupérer les tâches
@app.route("/api/v1/tasks", methods=["GET"])
@login_required
def get_tasks():
    con = get_db_connection()

    try:
        cur = con.cursor()
        user_id = session["user_id"] 

        cur.execute("SELECT * FROM task WHERE is_deleted = 0 AND user_id = ?",
        (user_id,)            
        )

        tasks = [dict(row) for row in cur.fetchall()]
        return jsonify(tasks)

    finally:
        con.close()


# Modifier une tâche
@app.route("/api/v1/tasks/<int:task_id>", methods=["PATCH"])
@login_required
def update_task(task_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify("error"), 400

    allowed_fields = {
        "title", "done", "important", "myday",
        "due", "listId", "note"
    }

    if not all(key in allowed_fields for key in data):
        return jsonify("error"), 400

    title = data.get("title")
    done = data.get("done")
    important = data.get("important")
    myday = data.get("myday")
    due = data.get("due")
    list_id = data.get("listId")
    note = data.get("note")

    for field in ("done", "important", "myday"):
        if field in data and not isinstance(data[field], bool):
            return jsonify("error"), 400

    if "title" in data:
        if not isinstance(title, str) or not title.strip():
            return jsonify("error"), 400

        title = title.strip()

        if len(title) > TAILLE_MAX_TASK_TITLE:
            return jsonify("error"), 400

    if "note" in data:
        if not isinstance(note, str):
            return jsonify("error"), 400

        if len(note) > TAILLE_MAX_NOTE:
            return jsonify("error"), 400

    if "due" in data and due is not None:
        if not isinstance(due, str) or len(due) != 10:
            return jsonify("error"), 400

        try:
            datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            return jsonify("error"), 400

    if "listId" in data and list_id is not None:
        if isinstance(list_id, bool) or not isinstance(list_id, int):
            return jsonify("error"), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        user_id = session["user_id"] 
        cur.execute(
            "SELECT * FROM task WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        task = cur.fetchone()

        if task is None:
            return jsonify("error"), 404

        if task["is_deleted"] == 1:
            return jsonify("error"), 404

        if "listId" in data and list_id is not None:
            cur.execute("SELECT id FROM list WHERE id = ? AND is_deleted = 0 AND user_id = ?", (list_id, user_id))

            if cur.fetchone() is None:
                return jsonify("error"), 404

        new_title = title if "title" in data else task["title"]
        new_done = int(done) if "done" in data else task["done"]
        new_important = (
            int(important) if "important" in data else task["important"]
        )
        new_myday = int(myday) if "myday" in data else task["myDay"]
        new_due = due if "due" in data else task["due"]
        new_list_id = list_id if "listId" in data else task["listId"]
        new_note = note if "note" in data else task["note"]

        cur.execute(
            """
            UPDATE task
            SET title = ?,
                done = ?,
                important = ?,
                myDay = ?,
                due = ?,
                listId = ?,
                note = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                new_title,
                new_done,
                new_important,
                new_myday,
                new_due,
                new_list_id,
                new_note,
                task_id,
                user_id
            )
        )

        con.commit()

        return jsonify({
            "message": "Tâche mise à jour",
            "id": task_id,
            "title": new_title,
            "done": bool(new_done),
            "important": bool(new_important),
            "myday": bool(new_myday),
            "due": new_due,
            "listId": new_list_id,
            "note": new_note
        }), 200

    except sqlite3.IntegrityError:
        con.rollback()
        return jsonify("error"), 400

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Supprimer une tâche
@app.route("/api/v1/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_tasks(task_id):
    con = get_db_connection()

    try:
        cur = con.cursor()
        deleted_at = int(time.time() * 1000)
        user_id = session["user_id"] 

        cur.execute(
            """
            UPDATE task
            SET is_deleted = 1, deletedAt = ?
            WHERE id = ? AND is_deleted = 0 AND user_id = ?
            """,
            (deleted_at, task_id, user_id)
        )

        if cur.rowcount == 0:
            return jsonify("error"), 404

        con.commit()
        return "", 204

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Supprimer une liste et les tâches qui lui sont associées
@app.route("/api/v1/lists/<int:list_id>", methods=["DELETE"])
@login_required
def delete_list(list_id):
    con = get_db_connection()
    user_id = session["user_id"] 

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT id FROM list WHERE id = ? AND is_deleted = 0 AND user_id = ?",
            (list_id, user_id)
        )

        liste = cur.fetchone()

        if liste is None:
            return jsonify("error"), 404

        deleted_at = int(time.time() * 1000)

        cur.execute(
            """
            UPDATE task
            SET is_deleted = 1, deletedAt = ?
            WHERE listId = ? AND is_deleted = 0 AND user_id = ?
            """,
            (deleted_at, list_id, user_id)
        )

        cur.execute(
            """
            UPDATE list
            SET is_deleted = 1, deletedAt = ?
            WHERE id = ? AND is_deleted = 0 AND user_id = ? 
            """,
            (deleted_at, list_id, user_id)
        )

        if cur.rowcount == 0:
            return jsonify("error"), 404

        con.commit()
        return "", 204

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Créer une sous-tâche
@app.route("/api/v1/tasks/<int:task_id>/steps", methods=["POST"])
@login_required
def create_step(task_id):
    data = request.get_json(silent=True)
    user_id = session["user_id"] 

    if not isinstance(data, dict):
        return jsonify("error"), 400

    title = data.get("title")

    if not isinstance(title, str) or not title.strip():
        return jsonify("error"), 400

    title = title.strip()

    if len(title) > TAILLE_MAX_STEP_TITLE:
        return jsonify("error"), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            "SELECT steps FROM task WHERE id = ? AND is_deleted = 0 AND user_id = ?",
            (task_id, user_id)
        )

        task = cur.fetchone()

        if task is None:
            return jsonify("error"), 404

        steps = json.loads(task["steps"])

        if len(steps) >= NOMBRE_MAX_STEPS:
            return jsonify("error"), 400

        new_step = {
            "id": str(uuid.uuid4()),
            "title": title,
            "done": False
        }

        steps.append(new_step)
        steps_json = json.dumps(steps)

        cur.execute(
            "UPDATE task SET steps = ? WHERE id = ? AND user_id = ?",
            (steps_json, task_id, user_id)
        )

        con.commit()

        return jsonify({
            "message": "Sous-tâche créée",
            "step": new_step
        }), 201

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Modifier une liste
@app.route("/api/v1/lists/<int:list_id>", methods=["PATCH"])
@login_required
def update_list(list_id):
    data = request.get_json(silent=True)
    user_id = session["user_id"] 

    if not isinstance(data, dict) or not data:
        return jsonify("error"), 400

    if not all(key in {"name"} for key in data):
        return jsonify("error"), 400

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        return jsonify("error"), 400

    name = name.strip()

    if len(name) > TAILLE_MAX_LIST_NAME:
        return jsonify("error"), 400

    con = get_db_connection()

    try:
        cur = con.cursor()

        cur.execute("BEGIN IMMEDIATE")

        cur.execute("SELECT id, is_deleted FROM list WHERE id = ? AND user_id = ?", (list_id, user_id))
        liste = cur.fetchone()

        if liste is None:
            return jsonify("error"), 404

        if liste["is_deleted"] == 1:
            return jsonify("error"), 404

        cur.execute(
            "UPDATE list SET name = ? WHERE id = ? AND user_id = ?",
            (name, list_id, user_id)
        )

        con.commit()

        return jsonify({
            "message": "Liste mise à jour",
            "id": list_id,
            "name": name
        }), 200

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Modifier une sous-tâche
@app.route("/api/v1/tasks/<int:id>/steps/<stepId>", methods=["PATCH"])
@login_required
def edit_steps(id, stepId):
    data = request.get_json(silent=True)
    user_id = session["user_id"] 

    if (
        not isinstance(data, dict)
        or not data
        or not ({"title", "done"} & data.keys())
        or not all(key in {"title", "done"} for key in data)
    ):
        return jsonify("error"), 400

    title = data.get("title")

    if "title" in data:
        if not isinstance(title, str) or not title.strip():
            return jsonify("error"), 400

        title = title.strip()

        if len(title) > TAILLE_MAX_STEP_TITLE:
            return jsonify("error"), 400

    if "done" in data and not isinstance(data["done"], bool):
        return jsonify("error"), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT steps, is_deleted FROM task WHERE id = ? AND user_id = ?", (id, user_id))
        task = cur.fetchone()

        if task is None:
            return jsonify("error"), 404

        if task["is_deleted"] == 1:
            return jsonify("error"), 404

        steps = json.loads(task["steps"])
        found_step = None

        for step in steps:
            if step["id"] == stepId:
                found_step = step
                if "title" in data:
                    step["title"] = title
                if "done" in data:
                    step["done"] = data["done"]
                break

        if found_step is None:
            return jsonify("error"), 404

        steps_json = json.dumps(steps)

        cur.execute(
            "UPDATE task SET steps = ? WHERE id = ? AND user_id = ?",
            (steps_json, id, user_id)
        )

        con.commit()

        return jsonify({
            "id": found_step["id"],
            "title": found_step["title"],
            "done": found_step["done"]
        }), 200

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Supprimer une sous-tâche
@app.route("/api/v1/tasks/<int:id>/steps/<stepId>", methods=["DELETE"])
@login_required
def sup_step(id, stepId):
    con = get_db_connection()
    user_id = session["user_id"] 

    try:
        cur = con.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT steps, is_deleted FROM task WHERE id = ? AND user_id = ?", (id, user_id))
        task = cur.fetchone()

        if task is None:
            return jsonify("error"), 404

        if task["is_deleted"] == 1:
            return jsonify("error"), 404

        steps = json.loads(task["steps"])
        step_to_delete = None

        for step in steps:
            if step["id"] == stepId:
                step_to_delete = step
                break

        if step_to_delete is None:
            return jsonify("error"), 404

        steps.remove(step_to_delete)
        steps_json = json.dumps(steps)

        cur.execute(
            "UPDATE task SET steps = ? WHERE id = ? AND user_id = ?",
            (steps_json, id, user_id)
        )

        con.commit()
        return "", 204

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Restaurer une tâche
@app.route("/api/v1/tasks/<int:task_id>/restore", methods=["POST"])
@login_required
def restore_task(task_id):
    user_id = session["user_id"] 

    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON invalide"}), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM task WHERE id = ? AND is_deleted = 1 AND user_id = ?",
            (task_id, user_id)
        )

        task = cur.fetchone()

        if task is None:
            return jsonify("error"), 404

        cur.execute(
            """
            UPDATE task
            SET is_deleted = 0, deletedAt = NULL
            WHERE id = ? AND is_deleted = 1 AND user_id = ?
            """,
            (task_id, user_id)
        )

        cur.execute(
            "SELECT * FROM task WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )

        restored_task = cur.fetchone()
        con.commit()

        return jsonify(dict(restored_task)), 200

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Restaurer une liste et les tâches supprimées avec elle
@app.route("/api/v1/lists/<int:list_id>/restore", methods=["POST"])
@login_required
def restore_list(list_id):
    user_id = session["user_id"] 

    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON invalide"}), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM list WHERE id = ? AND is_deleted = 1 AND user_id = ?",
            (list_id, user_id)
        )

        liste = cur.fetchone()

        if liste is None:
            return jsonify("error"), 404

        cur.execute(
            """
            UPDATE task
            SET is_deleted = 0, deletedAt = NULL
            WHERE listId = ?
              AND is_deleted = 1
              AND deletedAt = ?
              AND user_id = ?
            """,
            (list_id, liste["deletedAt"], user_id)
        )

        cur.execute(
            """
            UPDATE list
            SET is_deleted = 0, deletedAt = NULL
            WHERE id = ? AND is_deleted = 1 AND user_id = ?
            """,
            (list_id, user_id)
        )

        cur.execute(
            "SELECT * FROM list WHERE id = ? AND user_id = ?",
            (list_id, user_id)
        )

        restored_list = cur.fetchone()
        con.commit()

        return jsonify(dict(restored_list)), 200

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


# Création d'un utilisateur
@app.route("/api/v1/auth/register", methods=["POST"])
def register():

    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON invalide"}), 400

    # Récupération des informations ("username" envoyé par le front, "name" accepté aussi)
    name = data.get("username", data.get("name"))
    password = data.get("password")

    # Vérification des champs
    if not isinstance(name, str) or not isinstance(password, str):
        return jsonify({"error": "Nom et mot de passe requis"}), 400

    name = name.strip()

    if not name or not password:
        return jsonify({"error": "Nom et mot de passe requis"}), 400

    if len(name) > TAILLE_MAX_USERNAME:
        return jsonify({"error": "Nom d'utilisateur trop long"}), 400

    if len(password) < TAILLE_MIN_PASSWORD or len(password) > TAILLE_MAX_PASSWORD:
        return jsonify({"error": "Le mot de passe doit contenir au moins 8 caractères"}), 400

    # Connexion à la base de données
    con = get_db_connection()

    try:
        cur = con.cursor()

        # Vérification du nom d'utilisateur
        cur.execute(
            "SELECT ID FROM User WHERE name = ?",
            (name,)
        )
        user = cur.fetchone()

        if user is not None:
            return jsonify({"error": "Ce nom d'utilisateur existe déjà"}), 409

        # Hachage du mot de passe
        hashed_password = ph.hash(password)

        # Enregistrement du nouvel utilisateur
        cur.execute(
            "INSERT INTO User (name, password) VALUES (?, ?)",
            (name, hashed_password)
        )

        con.commit()

        return jsonify({"message": "Utilisateur créé avec succès"}), 201

    finally:
        con.close()


# Connexion d'un utilisateur
@app.route("/api/v1/auth/login", methods=["POST"])
def login():

    # Vérification du format JSON
    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON invalide"}), 400

    # Récupération des informations
    name = data.get("username")
    password = data.get("password")

    # Vérification des champs
    if not name or not password:
        return jsonify({"error": "Nom et mot de passe requis"}), 400

    # Connexion à la base de données
    con = get_db_connection()

    try:
        cur = con.cursor()

        # Recherche de l'utilisateur
        cur.execute(
            "SELECT ID, name, password FROM User WHERE name = ?",
            (name,)
        )

        user = cur.fetchone()

        # Vérification de l'existence de l'utilisateur
        if user is None:
            return jsonify({"error": "Identifiants incorrects"}), 401

        # Vérification du mot de passe
        try:
            ph.verify(user["password"], password)
        except VerifyMismatchError:
            return jsonify({"error": "Identifiants incorrects"}), 401

        # Vérification si le hachage doit être actualisé
        if ph.check_needs_rehash(user["password"]):
            new_hash = ph.hash(password)

            cur.execute(
                "UPDATE User SET password = ? WHERE ID = ?",
                (new_hash, user["ID"])
            )

            con.commit()

        # Création de la session
        session.clear()
        session["user_id"] = user["ID"]

        return jsonify({
            "message": "Connexion réussie",
            "username": user["name"]
        }), 200

    finally:
        con.close()


# Vérifier si un utilisateur est connecté
@app.route("/api/v1/auth/me", methods=["GET"])
def get_current_user():

    if "user_id" not in session:
        return jsonify({"error": "Non connecté"}), 401

    con = get_db_connection()

    try:
        cur = con.cursor()

        # Recherche de l'utilisateur connecté
        cur.execute(
            "SELECT ID, name FROM User WHERE ID = ?",
            (session["user_id"],)
        )

        user = cur.fetchone()

        if user is None:
            session.clear()
            return jsonify({"error": "Utilisateur introuvable"}), 401

        return jsonify({"username": user["name"]}), 200

    finally:
        con.close()


# Déconnexion d'un utilisateur
@app.route("/api/v1/auth/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({"message": "Déconnexion réussie"}), 200


# Changement du mot de passe de l'utilisateur connecté
@app.route("/api/v1/auth/change-password", methods=["POST"])
@login_required
def change_password():

    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON invalide"}), 400

    current_password = data.get("currentPassword")
    new_password = data.get("newPassword")

    if (
        not isinstance(current_password, str) or not current_password
        or not isinstance(new_password, str) or not new_password
    ):
        return jsonify({"error": "Mot de passe actuel et nouveau mot de passe requis"}), 400

    if len(new_password) < TAILLE_MIN_PASSWORD or len(new_password) > TAILLE_MAX_PASSWORD:
        return jsonify({"error": "Le nouveau mot de passe doit contenir au moins 8 caractères"}), 400

    if new_password == current_password:
        return jsonify({"error": "Le nouveau mot de passe doit être différent de l'actuel"}), 400

    con = get_db_connection()

    try:
        cur = con.cursor()

        cur.execute(
            "SELECT ID, password FROM User WHERE ID = ?",
            (session["user_id"],)
        )
        user = cur.fetchone()

        if user is None:
            session.clear()
            return jsonify({"error": "Utilisateur introuvable"}), 401

        # Vérification du mot de passe actuel (403 : la session, elle, reste valide)
        try:
            ph.verify(user["password"], current_password)
        except VerifyMismatchError:
            return jsonify({"error": "Mot de passe actuel incorrect"}), 403

        cur.execute(
            "UPDATE User SET password = ? WHERE ID = ?",
            (ph.hash(new_password), user["ID"])
        )

        con.commit()

        return jsonify({"message": "Mot de passe modifié"}), 200

    finally:
        con.close()



# Gestion des erreurs HTTP 
@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({
        "error": "Requête impossible"
    }), error.code or 500


# Gestion des erreurs inattendues
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Erreur interne non gérée")

    return jsonify({
        "error": "Une erreur interne est survenue"
    }), 500


debug = os.getenv("DEBUG", "False").lower() == "true"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9080, debug=debug)
