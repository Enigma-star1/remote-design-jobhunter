import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobhunter.db")

IS_POSTGRES = bool(DATABASE_URL)

if IS_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    # Render / Supabase sometimes provides postgres:// which psycopg2 prefers as postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    if IS_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(conn, query: str, params: tuple = ()):
    """Universal query runner converting ? to %s if on PostgreSQL"""
    if IS_POSTGRES:
        pg_query = query.replace("?", "%s")
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(pg_query, params)
        return cursor
    else:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if IS_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
            source TEXT,
            external_id TEXT UNIQUE,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            description TEXT,
            category TEXT,
            level TEXT,
            salary TEXT,
            is_worldwide INTEGER DEFAULT 1,
            date_posted TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS applications (
            id SERIAL PRIMARY KEY,
            job_id INTEGER,
            company TEXT,
            title TEXT,
            url TEXT,
            salary TEXT,
            status TEXT DEFAULT 'bookmarked',
            category TEXT,
            pitch_used TEXT,
            notes TEXT,
            applied_at TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        
        default_settings = {
            "telegram_token": "",
            "telegram_chat_id": "",
            "telegram_enabled": "false",
            "filter_category": "all",
            "filter_worldwide_only": "true"
        }
        for k, v in default_settings.items():
            cursor.execute("""
            INSERT INTO settings (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO NOTHING
            """, (k, v))
            
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            external_id TEXT UNIQUE,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            description TEXT,
            category TEXT,
            level TEXT,
            salary TEXT,
            is_worldwide INTEGER DEFAULT 1,
            date_posted TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            company TEXT,
            title TEXT,
            url TEXT,
            salary TEXT,
            status TEXT DEFAULT 'bookmarked',
            category TEXT,
            pitch_used TEXT,
            notes TEXT,
            applied_at TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        
        default_settings = {
            "telegram_token": "",
            "telegram_chat_id": "",
            "telegram_enabled": "false",
            "filter_category": "all",
            "filter_worldwide_only": "true"
        }
        for k, v in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
            
    # Automated cleanup: Purge any non-design roles from database
    disqualified = [
        "%sales%", "%recruit%", "%sourcer%", "%talent acquisition%", "%talent partner%",
        "%kernel%", "%linux%", "%software engineer%", "%electrical%", "%mechanical%",
        "%civil%", "%hardware%", "%netsuite%", "%salesforce%", "%compensation%",
        "%account executive%", "%account manager%", "%project manager%", "%program manager%",
        "%scrum master%", "%operations manager%", "%data engineer%", "%data science%",
        "%devops%", "%backend%", "%full stack%", "%qa%", "%quality assurance%",
        "%prosthetic%", "%orthotic%", "%interior%", "%carpenter%", "%landscape%"
    ]
    for dq in disqualified:
        if IS_POSTGRES:
            cursor.execute("DELETE FROM jobs WHERE title ILIKE %s", (dq,))
        else:
            cursor.execute("DELETE FROM jobs WHERE title LIKE ?", (dq,))

    conn.commit()
    conn.close()

def save_job(job_data: Dict[str, Any]) -> bool:
    """Save a job if it doesn't already exist. Returns True if newly inserted."""
    conn = get_db_connection()
    try:
        params = (
            job_data.get("source", "Web"),
            job_data.get("external_id", job_data.get("url", "")),
            job_data.get("title", ""),
            job_data.get("company", ""),
            job_data.get("location", "Remote (Worldwide)"),
            job_data.get("url", ""),
            job_data.get("description", ""),
            job_data.get("category", "General Design"),
            job_data.get("level", "All Levels"),
            job_data.get("salary", "Disclosed on Apply"),
            1 if job_data.get("is_worldwide", True) else 0,
            job_data.get("date_posted", datetime.utcnow().strftime("%Y-%m-%d"))
        )
        
        if IS_POSTGRES:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO jobs (source, external_id, title, company, location, url, description, category, level, salary, is_worldwide, date_posted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (external_id) DO NOTHING
            """, params)
            inserted = cursor.rowcount > 0
        else:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO jobs (source, external_id, title, company, location, url, description, category, level, salary, is_worldwide, date_posted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, params)
            inserted = True
            
        conn.commit()
        return inserted
    except Exception:
        return False
    finally:
        conn.close()

def get_jobs(
    search: str = "", 
    category: str = "", 
    level: str = "", 
    worldwide_only: bool = False, 
    date_filter: str = "all",
    exclude_applied: bool = True,
    limit: int = 200
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    
    if exclude_applied:
        query += """ AND id NOT IN (SELECT job_id FROM applications WHERE job_id IS NOT NULL)
                     AND url NOT IN (SELECT url FROM applications WHERE url IS NOT NULL AND url != '')"""
        
    if search:
        query += " AND (title ILIKE ? OR company ILIKE ? OR description ILIKE ? OR source ILIKE ?)" if IS_POSTGRES else " AND (title LIKE ? OR company LIKE ? OR description LIKE ? OR source LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
        
    if category and category.lower() != "all":
        query += " AND category ILIKE ?" if IS_POSTGRES else " AND category LIKE ?"
        params.append(f"%{category}%")
        
    if level and level.lower() != "all":
        query += " AND level ILIKE ?" if IS_POSTGRES else " AND level LIKE ?"
        params.append(f"%{level}%")
        
    if worldwide_only:
        query += " AND is_worldwide = 1"
        
    if date_filter == "today":
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        query += " AND date_posted >= ?"
        params.append(today_str)
    elif date_filter == "3days":
        query += " AND date_posted >= (CURRENT_DATE - INTERVAL '3 days')::text" if IS_POSTGRES else " AND date_posted >= date('now', '-3 days')"
    elif date_filter == "7days":
        query += " AND date_posted >= (CURRENT_DATE - INTERVAL '7 days')::text" if IS_POSTGRES else " AND date_posted >= date('now', '-7 days')"
    
    # Guarantee no non-design roles ever display
    strict_disqualified = [
        "%sales%", "%recruit%", "%sourcer%", "%talent acquisition%", "%talent partner%",
        "%kernel%", "%linux%", "%software engineer%", "%electrical%", "%mechanical%",
        "%civil%", "%hardware%", "%netsuite%", "%salesforce%", "%compensation%",
        "%account executive%", "%account manager%", "%project manager%", "%program manager%",
        "%scrum master%", "%operations manager%", "%data engineer%", "%data science%",
        "%devops%", "%backend%", "%full stack%", "%qa%", "%quality assurance%",
        "%prosthetic%", "%orthotic%", "%interior%", "%carpenter%", "%landscape%"
    ]
    for dq in strict_disqualified:
        query += " AND title NOT ILIKE ?" if IS_POSTGRES else " AND title NOT LIKE ?"
        params.append(dq)

    query += " ORDER BY date_posted DESC, id DESC LIMIT ?"
    params.append(limit)
    
    cursor = execute_query(conn, query, tuple(params))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_applications() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = execute_query(conn, "SELECT * FROM applications ORDER BY updated_at DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def add_application(app_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    params = (
        app_data.get("job_id"),
        app_data.get("company", ""),
        app_data.get("title", ""),
        app_data.get("url", ""),
        app_data.get("salary", ""),
        app_data.get("status", "bookmarked"),
        app_data.get("category", "UI/UX"),
        app_data.get("pitch_used", ""),
        app_data.get("notes", ""),
        app_data.get("applied_at", datetime.utcnow().strftime("%Y-%m-%d"))
    )
    
    if IS_POSTGRES:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO applications (job_id, company, title, url, salary, status, category, pitch_used, notes, applied_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """, params)
        app_id = cursor.fetchone()[0]
    else:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO applications (job_id, company, title, url, salary, status, category, pitch_used, notes, applied_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        app_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return app_id

def update_application_status(app_id: int, status: str, notes: Optional[str] = None):
    conn = get_db_connection()
    if notes is not None:
        query = """
        UPDATE applications 
        SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
        """
        execute_query(conn, query, (status, notes, app_id))
    else:
        query = """
        UPDATE applications 
        SET status = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
        """
        execute_query(conn, query, (status, app_id))
    conn.commit()
    conn.close()

def delete_application(app_id: int):
    conn = get_db_connection()
    execute_query(conn, "DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()

def get_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = execute_query(conn, "SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def update_setting(key: str, value: str):
    conn = get_db_connection()
    if IS_POSTGRES:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, str(value)))
    else:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
