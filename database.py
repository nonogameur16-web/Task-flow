import sqlite3
con = sqlite3.connect("Data_base.db")
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


con.commit()
