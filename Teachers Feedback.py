import streamlit as st
import pandas as pd
import plotly.express as px
import mysql.connector
from mysql.connector import Error

# Load credentials securely from Streamlit Cloud Secrets
DB_CONFIG = {
    "host": st.secrets["mysql"]["host"],
    "user": st.secrets["mysql"]["user"],
    "password": st.secrets["mysql"]["password"],
    "database": st.secrets["mysql"]["database"],
    "port": int(st.secrets["mysql"]["port"]),
    "ssl_disabled": False
}

# 1. CACHE THE DATABASE CONNECTION (Makes the whole app instant!)
@st.cache_resource
def get_db_connection():
    """Creates a single persistent connection pool to Aiven."""
    return mysql.connector.connect(**DB_CONFIG)

def get_active_conn():
    """Helper that auto-reconnects if Aiven drops the socket."""
    conn = get_db_connection()
    if not conn.is_connected():
        conn.reconnect(attempts=3, delay=1)
    return conn

def init_db():
    """Initializes database tables ONCE during startup."""
    try:
        conn = get_active_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(50) PRIMARY KEY,
                password VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL,
                name VARCHAR(100) NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                teacher_id VARCHAR(50) NOT NULL,
                teacher_name VARCHAR(100) NOT NULL,
                student_name VARCHAR(100) NOT NULL,
                performance VARCHAR(20) NOT NULL,
                stars INT NOT NULL,
                review TEXT
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            default_users = [
                ("admin", "admin123", "Admin", "System Admin"),
                ("T101", "teach123", "Teacher", "Dr. S.Uma"),
                ("T102", "teach123", "Teacher", "Prof. K.Arun"),
                ("T103", "teach123", "Teacher", "Dr. P.Anu"),
                ("T104", "teach123", "Teacher", "Prof. S.Senthil"),
                ("T105", "teach123", "Teacher", "Dr. K.Priya"),
                ("T106", "teach123", "Teacher", "Dr. S.Maheshwari")
            ]
            cursor.executemany(
                "INSERT INTO users (username, password, role, name) VALUES (%s, %s, %s, %s)",
                default_users
            )
            conn.commit()

        cursor.close()
    except Error as e:
        st.error(f"Error during Database Initialization: {e}")

# Run database setup ONCE
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# 2. CACHE HEAVY QUERIES (Prevents slow SQL queries on every click)
@st.cache_data(ttl=30)
def get_top_teacher():
    """Queries database dynamically to calculate top-rated teacher(s)."""
    try:
        conn = get_active_conn()
        query = """
            SELECT teacher_id, teacher_name, AVG(stars) as avg_stars 
            FROM feedback 
            GROUP BY teacher_id, teacher_name 
            ORDER BY avg_stars DESC
        """
        df = pd.read_sql(query, conn)

        if df.empty:
            return "N/A", "N/A", 0.0

        max_rating = df["avg_stars"].max()
        top_teachers_df = df[df["avg_stars"] == max_rating]

        names = ", ".join(top_teachers_df["teacher_name"].tolist())
        ids = ", ".join(top_teachers_df["teacher_id"].tolist())

        return names, ids, round(max_rating, 2)
    except Exception:
        return "N/A", "N/A", 0.0
