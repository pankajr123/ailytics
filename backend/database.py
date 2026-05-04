import sqlite3

DB_PATH = "saas_data.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY,
                name TEXT,
                plan TEXT,
                country TEXT,
                joined_date TEXT
            );
            CREATE TABLE IF NOT EXISTS revenue (
                id INTEGER PRIMARY KEY,
                client_id INTEGER,
                amount REAL,
                month TEXT,
                status TEXT
            );
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY,
                client_id INTEGER,
                issue TEXT,
                priority TEXT,
                status TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY,
                client_id INTEGER,
                feature TEXT,
                usage_count INTEGER,
                month TEXT
            );
            CREATE TABLE IF NOT EXISTS uploaded_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT
            );
        """)
        conn.commit()
    finally:
        conn.close()