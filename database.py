import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data_base.db")
con = sqlite3.connect(DB_PATH)
con.execute("PRAGMA foreign_keys = ON")

cur = con.cursor()

#CREATION DE TABLES
cur.execute("CREATE TABLE IF NOT EXISTS list(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, theme TEXT)")
cur.execute("""
    CREATE TABLE IF NOT EXISTS task (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        done INTEGER NOT NULL DEFAULT 0,
        important INTEGER NOT NULL DEFAULT 0,
        myDay INTEGER NOT NULL DEFAULT 0,
        due TEXT,
        listId INTEGER,
        steps TEXT NOT NULL DEFAULT '[]',
        note TEXT NOT NULL DEFAULT '',
        createdAt INTEGER NOT NULL,
        completedAt INTEGER,
        FOREIGN KEY (listId) REFERENCES list(id)
    )
""")
cur.execute("""
    CREATE TABLE IF NOT EXISTS User (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        password TEXT NOT NULL
    )
""")

def add_column_if_not_exists(cur, table, column, definition):
    columns = [row[1] for row in cur.execute(f"PRAGMA table_info({table})")]

    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

add_column_if_not_exists(cur, "list", "user_id", "INTEGER")
add_column_if_not_exists(cur, "task", "user_id", "INTEGER")

cur.execute("PRAGMA table_info(list)")
list_columns = [row[1] for row in cur.fetchall()]

if "is_deleted" not in list_columns:
    cur.execute("ALTER TABLE list ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")

if "deletedAt" not in list_columns:
    cur.execute("ALTER TABLE list ADD COLUMN deletedAt INTEGER")

cur.execute("PRAGMA table_info(task)")
task_columns = [row[1] for row in cur.fetchall()]

if "is_deleted" not in task_columns:
    cur.execute("ALTER TABLE task ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")

if "deletedAt" not in task_columns:
    cur.execute("ALTER TABLE task ADD COLUMN deletedAt INTEGER")


# Protection anti-brute-force des inscriptions
cur.execute("""
    CREATE TABLE IF NOT EXISTS registration_security (
        ip_hash TEXT PRIMARY KEY,
        attempts INTEGER NOT NULL DEFAULT 0,
        window_started_at INTEGER NOT NULL,
        blocked_until INTEGER NOT NULL DEFAULT 0,
        last_attempt_at INTEGER NOT NULL
    )
""")


# Protection anti-brute-force de la connexion
cur.execute("""
    CREATE TABLE IF NOT EXISTS login_security (
        scope TEXT NOT NULL,
        key_hash TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        window_started_at INTEGER NOT NULL,
        blocked_until INTEGER NOT NULL DEFAULT 0,
        last_attempt_at INTEGER NOT NULL,
        PRIMARY KEY (scope, key_hash)
    )
""")



con.commit()
