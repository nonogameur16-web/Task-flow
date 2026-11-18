from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from datetime import datetime
from dotenv import load_dotenv
import sqlite3
import time
import json
import uuid
import os


load_dotenv()
app = Flask(__name__, static_folder="web", static_url_path="")
app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost"]
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

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


# Connexion commune à la base de données
def get_db_connection():
    con = sqlite3.connect("Data_base.db", timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = "script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/", methods=["GET"])
def index():
    return send_from_directory("web", "index.html")


# Récupérer les listes
@app.route("/api/v1/lists", methods=["GET"])
def get_lists():
    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT id, name, theme FROM list WHERE is_deleted = 0"
        )

        lists = [dict(row) for row in cur.fetchall()]
        return jsonify(lists)

    finally:
        con.close()


# Créer une liste
@app.route("/api/v1/lists", methods=["POST"])
def create_list():
    data = request.get_json(silent=True)

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
            INSERT INTO list (name, theme)
            VALUES (?, ?)
            """,
            (name, theme)
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

        if list_id is not None:
            cur.execute(
                "SELECT id, is_deleted FROM list WHERE id = ?",
                (list_id,)
            )

            destination_list = cur.fetchone()

            if destination_list is None:
                return jsonify("error"), 404

            if destination_list["is_deleted"] == 1:
                return jsonify("error"), 404
            
        cur.execute(
            """
            INSERT INTO task
                (title, done, important, myDay, due, listId, createdAt)
            VALUES (?, 0, ?, ?, ?, ?, ?)
            """,
            (title, important, my_day, due, list_id, created_at)
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
def get_tasks():
    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM task WHERE is_deleted = 0")

        tasks = [dict(row) for row in cur.fetchall()]
        return jsonify(tasks)

    finally:
        con.close()


# Modifier une tâche
@app.route("/api/v1/tasks/<int:task_id>", methods=["PATCH"])
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
        cur.execute("SELECT * FROM task WHERE id = ?", (task_id,))
        task = cur.fetchone()

        if task is None:
            return jsonify("error"), 404

        if task["is_deleted"] == 1:
            return jsonify("error"), 404

        if "listId" in data and list_id is not None:
            cur.execute("SELECT id FROM list WHERE id = ? AND is_deleted = 0", (list_id,))

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
            WHERE id = ?
            """,
            (
                new_title,
                new_done,
                new_important,
                new_myday,
                new_due,
                new_list_id,
                new_note,
                task_id
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
def delete_tasks(task_id):
    con = get_db_connection()

    try:
        cur = con.cursor()
        deleted_at = int(time.time() * 1000)

        cur.execute(
            """
            UPDATE task
            SET is_deleted = 1, deletedAt = ?
            WHERE id = ? AND is_deleted = 0
            """,
            (deleted_at, task_id)
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
def delete_list(list_id):
    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT id FROM list WHERE id = ? AND is_deleted = 0",
            (list_id,)
        )

        liste = cur.fetchone()

        if liste is None:
            return jsonify("error"), 404

        deleted_at = int(time.time() * 1000)

        cur.execute(
            """
            UPDATE task
            SET is_deleted = 1, deletedAt = ?
            WHERE listId = ? AND is_deleted = 0
            """,
            (deleted_at, list_id)
        )

        cur.execute(
            """
            UPDATE list
            SET is_deleted = 1, deletedAt = ?
            WHERE id = ? AND is_deleted = 0
            """,
            (deleted_at, list_id)
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
def create_step(task_id):
    data = request.get_json(silent=True)

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
            "SELECT steps FROM task WHERE id = ? AND is_deleted = 0",
            (task_id,)
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
            "UPDATE task SET steps = ? WHERE id = ?",
            (steps_json, task_id)
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
def update_list(list_id):
    data = request.get_json(silent=True)

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

        cur.execute("SELECT id, is_deleted FROM list WHERE id = ?", (list_id,))
        liste = cur.fetchone()

        if liste is None:
            return jsonify("error"), 404

        if liste["is_deleted"] == 1:
            return jsonify("error"), 404

        cur.execute(
            "UPDATE list SET name = ? WHERE id = ?",
            (name, list_id)
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
def edit_steps(id, stepId):
    data = request.get_json(silent=True)

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
        cur.execute("SELECT steps, is_deleted FROM task WHERE id = ?", (id,))
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
            "UPDATE task SET steps = ? WHERE id = ?",
            (steps_json, id)
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
def sup_step(id, stepId):
    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT steps, is_deleted FROM task WHERE id = ?", (id,))
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
            "UPDATE task SET steps = ? WHERE id = ?",
            (steps_json, id)
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
def restore_task(task_id):

    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON invalide"}), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM task WHERE id = ? AND is_deleted = 1",
            (task_id,)
        )

        task = cur.fetchone()

        if task is None:
            return jsonify("error"), 404

        cur.execute(
            """
            UPDATE task
            SET is_deleted = 0, deletedAt = NULL
            WHERE id = ? AND is_deleted = 1
            """,
            (task_id,)
        )

        cur.execute(
            "SELECT * FROM task WHERE id = ?",
            (task_id,)
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
def restore_list(list_id):

    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON invalide"}), 400

    con = get_db_connection()

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM list WHERE id = ? AND is_deleted = 1",
            (list_id,)
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
            """,
            (list_id, liste["deletedAt"])
        )

        cur.execute(
            """
            UPDATE list
            SET is_deleted = 0, deletedAt = NULL
            WHERE id = ? AND is_deleted = 1
            """,
            (list_id,)
        )

        cur.execute(
            "SELECT * FROM list WHERE id = ?",
            (list_id,)
        )

        restored_list = cur.fetchone()
        con.commit()

        return jsonify(dict(restored_list)), 200

    except Exception:
        con.rollback()
        raise

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
