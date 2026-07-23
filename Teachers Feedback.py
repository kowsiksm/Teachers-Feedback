import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3

# ------------------------------------------------------------------------------
# 1. DATABASE CONFIGURATION (SQLITE)
# ------------------------------------------------------------------------------
DB_FILE = "feedback_portal.db"

def get_db_connection():
    """Establishes connection to the local SQLite file."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enables dict-like access for columns
    return conn

def init_db():
    """Initializes the SQLite database tables and seeds default data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)

    # Feedback table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id TEXT NOT NULL,
            teacher_name TEXT NOT NULL,
            student_name TEXT NOT NULL,
            performance TEXT NOT NULL,
            stars INTEGER NOT NULL,
            review TEXT
        )
    """)

    # Seed default users
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
            "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
            default_users
        )
        conn.commit()

    # Seed default feedback
    cursor.execute("SELECT COUNT(*) FROM feedback")
    if cursor.fetchone()[0] == 0:
        default_feedback = [
            ("T101", "Dr. S.Uma", "Rahul", "Good", 5, "Excellent teaching style, very clear concepts."),
            ("T101", "Dr. S.Uma", "Ananya", "Good", 4, "Great professor, very approachable."),
            ("T102", "Prof. K.Arun", "Rahul", "Moderate", 3, "Good, but moves through the slides a bit too fast."),
            ("T103", "Dr. P.Anu", "Ananya", "Good", 5, "The absolute best at coding examples.")
        ]
        cursor.executemany(
            "INSERT INTO feedback (teacher_id, teacher_name, student_name, performance, stars, review) VALUES (?, ?, ?, ?, ?, ?)",
            default_feedback
        )
        conn.commit()

    cursor.close()
    conn.close()
