import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "enterprise_compliance.db")

def get_connection():
    """Returns a SQLite connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    """Creates the compliance_ledger table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compliance_ledger (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_complaint       TEXT NOT NULL,
            masked_complaint    TEXT NOT NULL,
            risk_category       TEXT NOT NULL,
            tat_deadline        TEXT NOT NULL,
            accrued_penalty     INTEGER DEFAULT 0,
            complaint_age_days  INTEGER DEFAULT 0,
            overdue_days        INTEGER DEFAULT 0,
            status              TEXT DEFAULT 'OPEN',
            ai_summary          TEXT,
            ai_urgency          TEXT,
            agent_script        TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def insert_record(data: dict):
    """Inserts a processed complaint record into the ledger."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO compliance_ledger (
                raw_complaint, masked_complaint, risk_category,
                tat_deadline, accrued_penalty, complaint_age_days,
                overdue_days, status, ai_summary, ai_urgency, agent_script
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get("raw_complaint"),
            data.get("masked_complaint"),
            data.get("risk_category"),
            data.get("tat_deadline"),
            data.get("accrued_penalty", 0),
            data.get("complaint_age_days", 0),
            data.get("overdue_days", 0),
            data.get("status", "OPEN"),
            data.get("ai_summary"),
            data.get("ai_urgency"),
            data.get("agent_script")
        ))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Database insert error: {e}")
        return None
    finally:
        conn.close()

def fetch_all_records():
    """Returns all records ordered newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT * FROM compliance_ledger
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Database fetch error: {e}")
        return []
    finally:
        conn.close()

# Run this file directly to initialize the database
if __name__ == "__main__":
    initialize_db()