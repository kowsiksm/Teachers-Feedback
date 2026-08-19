import streamlit as st
import pandas as pd
import plotly.express as px
import mysql.connector
from mysql.connector import Error

# 1. MUST BE THE VERY FIRST STREAMLIT COMMAND IN THE SCRIPT
st.set_page_config(page_title="Teacher Feedback Portal", layout="wide")

# 2. Database credentials from Streamlit Secrets
DB_CONFIG = {
    "host": st.secrets["mysql"]["host"],
    "user": st.secrets["mysql"]["user"],
    "password": st.secrets["mysql"]["password"],
    "database": st.secrets["mysql"]["database"],
    "port": int(st.secrets["mysql"]["port"]),
    "ssl_disabled": False
}

# 3. Cached connection pool for instant loading
@st.cache_resource
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def get_active_conn():
    conn = get_db_connection()
    if not conn.is_connected():
        conn.reconnect(attempts=3, delay=1)
    return conn

def init_db():
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
                ("T102", "teach123", "Teacher", "Prof. K. Arun"),
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

# Run database setup safely
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

@st.cache_data(ttl=30)
def get_top_teacher():
    try:
        conn = get_active_conn()
        query = """
            SELECT teacher_name, AVG(stars) as avg_stars 
            FROM feedback 
            GROUP BY teacher_id, teacher_name 
            ORDER BY avg_stars DESC
        """
        df = pd.read_sql(query, conn)

        if df.empty:
            return "N/A", 0.0

        max_rating = df["avg_stars"].max()
        top_teachers_df = df[df["avg_stars"] == max_rating]

        names = ", ".join(top_teachers_df["teacher_name"].tolist())
        return names, round(max_rating, 2)
    except Exception:
        return "N/A", 0.0

# Top Header Banner
st.title("🎓 Teacher Performance Feedback Portal")
top_name, top_rating = get_top_teacher()
st.info(f"🏆 **Top Ranked Teacher:** {top_name} | ⭐ **Avg Rating:** {top_rating}/5")
st.markdown("---")

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

# --- LOGIN SCREEN ---
if st.session_state.logged_in_user is None:
    st.subheader("🔑 Portal Gateways")
    col_login1, col_login2 = st.columns(2)

    with col_login1:
        st.info("### 📝 Student Login Dashboard\nStudents enter assigned Roll Number ID and password parameters here.")
    with col_login2:
        st.warning("### 🛠️ Admin / Teacher Login Desk\nAdministrative supervisors and academic faculty log in here.")

    st.markdown("<br>", unsafe_allow_html=True)

    with st.form("login_form"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("User ID / Username / Roll No")
        with col2:
            password = st.text_input("Password", type="password")

        submit_login = st.form_submit_button("Login securely to System", use_container_width=True)

    if submit_login:
        try:
            conn = get_active_conn()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
            user_record = cursor.fetchone()
            cursor.close()

            if user_record:
                st.session_state.logged_in_user = user_record
                st.rerun()
            else:
                st.error("Invalid Credentials. Please check ID and Password.")
        except Error as e:
            st.error(f"Database error during login: {e}")

# --- DASHBOARDS AFTER LOGIN ---
else:
    user_info = st.session_state.logged_in_user
    st.sidebar.markdown(f"### Welcome, **{user_info['name']}**")
    st.sidebar.markdown(f"**Role:** `{user_info['role']}`")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.logged_in_user = None
        st.rerun()

    # 1. ADMIN DASHBOARD
    if user_info["role"] == "Admin":
        st.header("🛠️ Admin Console & Institutional Insights")

        try:
            conn = get_active_conn()
            df_all = pd.read_sql("SELECT * FROM feedback", conn)
        except Exception as e:
            df_all = pd.DataFrame()
            st.error(f"Failed to fetch feedback logs: {e}")

        if not df_all.empty:
            st.subheader("📊 Faculty Quality Rankings Leaderboard")

            # Clean whitespace and standardize teacher names
            df_all["teacher_name"] = df_all["teacher_name"].str.strip().str.title()

            # Group strictly by teacher_id so unique IDs combine all entries into one bar
            ranking_metrics = df_all.groupby("teacher_id").agg(
                teacher_name=("teacher_name", "first"),
                avg_stars=("stars", "mean"),
                total_reviews=("stars", "count"),
                students=("student_name", lambda x: ", ".join(x.unique()))
            ).reset_index().sort_values(by="avg_stars", ascending=False)

            ranking_metrics["Rank"] = range(1, len(ranking_metrics) + 1)

            fig_ranking = px.bar(
                ranking_metrics,
                x="teacher_name",
                y="avg_stars",
                title="Official Teacher Performance Ranking (Higher is Better)",
                labels={
                    "avg_stars": "Average Rating Score",
                    "teacher_name": "Faculty Member Name",
                    "Rank": "Leaderboard Rank",
                    "total_reviews": "Total Students Voted",
                    "students": "Voted By"
                },
                color="avg_stars",
                color_continuous_scale="turbo",
                text="avg_stars",
                hover_data=["Rank", "total_reviews", "students"]
            )
            fig_ranking.update_traces(texttemplate='%{text:.2f} ⭐', textposition='outside')
            fig_ranking.update_layout(yaxis_range=[0, 5.5], height=380)
            st.plotly_chart(fig_ranking, use_container_width=True)

            st.subheader("📥 Export Institutional Insights Data")
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                csv_raw_feedback = df_all.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Master Feedback Log (CSV)",
                    data=csv_raw_feedback,
                    file_name="master_feedback_log.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col_exp2:
                csv_summary_metrics = ranking_metrics.drop(columns=["students"]).to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Aggregated Performance Report (CSV)",
                    data=csv_summary_metrics,
                    file_name="aggregated_teacher_performance.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            st.markdown("---")

        col1, col2 = st.columns([1, 1])
        with col1:
            with st.form("add_user_form", clear_on_submit=True):
                st.subheader("➕ Dynamic User & Student Onboarding")
                new_uid = st.text_input("User ID / Roll Number (e.g., S101, S102, T107)")
                new_name = st.text_input("Full Name")
                new_pass = st.text_input("Setup Temporary Password", type="password")
                new_role = st.selectbox("Assign System Role", ["Student", "Teacher"])

                submit_user = st.form_submit_button("Save & Grant System Access")
                if submit_user:
                    if not new_uid.strip() or not new_name.strip() or not new_pass.strip():
                        st.error("All input metrics are mandatory to register a user.")
                    else:
                        try:
                            conn = get_active_conn()
                            cursor = conn.cursor()
                            cursor.execute("SELECT username FROM users WHERE username = %s", (new_uid,))
                            if cursor.fetchone():
                                st.warning(f"Registration failure. User ID '{new_uid}' is already assigned.")
                            else:
                                cursor.execute(
                                    "INSERT INTO users (username, password, role, name) VALUES (%s, %s, %s, %s)",
                                    (new_uid, new_pass, new_role, new_name)
                                )
                                conn.commit()
                                st.success(f"Successfully registered {new_name} as a dynamic {new_role} record!")
                                st.rerun()
                            cursor.close()
                        except Error as e:
                            st.error(f"Failed to create user: {e}")

        with col2:
            st.subheader("📋 Dynamic System Users Directory")
            try:
                conn = get_active_conn()
                users_df = pd.read_sql("SELECT username as `User ID`, name as `Name`, role as `Role` FROM users", conn)
            except Exception as e:
                users_df = pd.DataFrame(columns=["User ID", "Name", "Role"])
                st.error(f"Failed to fetch user directory: {e}")

            tab_all, tab_students, tab_teachers = st.tabs(["All Users", "Students Only", "Teachers Only"])
            with tab_all:
                st.dataframe(users_df, use_container_width=True, height=200, hide_index=True)
            with tab_students:
                st.dataframe(users_df[users_df["Role"] == "Student"][["User ID", "Name"]], use_container_width=True, height=200, hide_index=True)
            with tab_teachers:
                st.dataframe(users_df[users_df["Role"] == "Teacher"][["User ID", "Name"]], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("🗑️ Danger Zone: Remove User Record")
            del_uid = st.text_input("Enter User ID to Delete (e.g., S101)", key="delete_uid_input")
            if st.button("Delete User Instantly", type="primary", use_container_width=True):
                if not del_uid.strip():
                    st.error("Please enter a valid User ID.")
                elif del_uid == "admin":
                    st.error("Security Rule: System Admin record cannot be destroyed.")
                else:
                    try:
                        conn = get_active_conn()
                        cursor = conn.cursor()
                        cursor.execute("SELECT name, role FROM users WHERE username = %s", (del_uid,))
                        target_user = cursor.fetchone()

                        if target_user:
                            cursor.execute("DELETE FROM users WHERE username = %s", (del_uid,))
                            conn.commit()
                            st.success(f"Successfully deleted {target_user[0]} [{target_user[1]}] from the system.")
                            st.rerun()
                        else:
                            st.error(f"User ID '{del_uid}' not found in active directory database.")
                        cursor.close()
                    except Error as e:
                        st.error(f"Error during deletion: {e}")

    # 2. STUDENT DASHBOARD
    elif user_info["role"] == "Student":
        st.header("📝 Submit Teacher Feedback Matrix")

        try:
            conn = get_active_conn()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT username, name FROM users WHERE role = 'Teacher'")
            teachers_list = {row["username"]: row["name"] for row in cursor.fetchall()}
            cursor.close()
        except Error as e:
            teachers_list = {}
            st.error(f"Failed to fetch faculty list: {e}")

        if not teachers_list:
            st.warning("No teachers registered in the system yet.")
        else:
            with st.form("feedback_form", clear_on_submit=True):
                selected_teacher_id = st.selectbox("Select Teacher", list(teachers_list.keys()), format_func=lambda x: f"{teachers_list[x]} ({x})")

                st.markdown("### 📊 Performance Assessment Matrix")
                st.markdown("Please evaluate your instructor honestly across the following indicators:")

                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    m_lecturing = st.selectbox("📖 Lecturing Quality & Explanation", [5, 4, 3, 2, 1], format_func=lambda x: f"{x} Stars")
                    m_discipline = st.selectbox("📐 Maintaining Discipline & Classroom Control", [5, 4, 3, 2, 1], format_func=lambda x: f"{x} Stars")
                    m_portion = st.selectbox("⏱️ Completing Portion & Syllabus Schedule", [5, 4, 3, 2, 1], format_func=lambda x: f"{x} Stars")
                with col_m2:
                    m_impression = st.selectbox("🤝 General Impression Between Students", [5, 4, 3, 2, 1], format_func=lambda x: f"{x} Stars")
                    m_communication = st.selectbox("🗣️ Communication Skills & Approachability", [5, 4, 3, 2, 1], format_func=lambda x: f"{x} Stars")

                st.markdown("---")
                st.write("Overall Score Star Selection (Optional override link):")
                star_input = st.feedback("stars")

                review_text = st.text_area("Paragraph Review / Detailed Comments", placeholder="Provide constructive feedback here regarding lessons...")

                submit_feedback = st.form_submit_button("Submit Structured Feedback")
                if submit_feedback:
                    calculated_avg = (m_lecturing + m_discipline + m_portion + m_impression + m_communication) / 5

                    if calculated_avg >= 4.0:
                        performance_classification = "Good"
                    elif calculated_avg >= 2.5:
                        performance_classification = "Moderate"
                    else:
                        performance_classification = "Low"

                    final_stars = (star_input + 1) if star_input is not None else round(calculated_avg)
                    detailed_review = f"[Lecturing: {m_lecturing}/5, Discipline: {m_discipline}/5, Portion: {m_portion}/5, Impression: {m_impression}/5, Communication: {m_communication}/5] {review_text}"

                    try:
                        conn = get_active_conn()
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO feedback (teacher_id, teacher_name, student_name, performance, stars, review) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (selected_teacher_id, teachers_list[selected_teacher_id], user_info["name"], performance_classification, final_stars, detailed_review))
                        conn.commit()
                        cursor.close()
                        st.success("Thank you! Your feedback matrix has been securely processed.")
                        st.rerun()
                    except Error as e:
                        st.error(f"Failed to submit feedback: {e}")

            st.markdown("---")
            st.subheader("📊 Your Feedback History")

            try:
                conn = get_active_conn()
                df_student_history = pd.read_sql(
                    "SELECT teacher_id, teacher_name, performance, stars, review FROM feedback WHERE student_name = %s", 
                    conn, 
                    params=(user_info["name"],)
                )
            except Exception as e:
                df_student_history = pd.DataFrame()
                st.error(f"Could not load your history: {e}")

            if df_student_history.empty:
                st.info("You haven't submitted any feedback forms yet.")
            else:
                display_history = df_student_history.copy()
                display_history.columns = ["Teacher ID", "Teacher Name", "Classification", "Stars Given", "Your Logged Review Metrics"]
                st.dataframe(display_history, use_container_width=True, hide_index=True)

                csv_student = display_history.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download My Submission History (CSV)",
                    data=csv_student,
                    file_name=f"my_submitted_feedback_{user_info['username']}.csv",
                    mime="text/csv"
                )

    # 3. TEACHER DASHBOARD
    elif user_info["role"] == "Teacher":
        teacher_name = user_info["name"]
        st.header("📊 Feedback Performance Insights")

        try:
            conn = get_active_conn()
            df_teacher = pd.read_sql("SELECT * FROM feedback WHERE teacher_name = %s", conn, params=(teacher_name,))
        except Exception as e:
            df_teacher = pd.DataFrame()
            st.error(f"Failed to fetch performance records: {e}")

        if df_teacher.empty:
            st.info("No feedback has been submitted for you yet.")
        else:
            avg_stars = df_teacher["stars"].mean()
            col1, col2 = st.columns(2)
            col1.metric("Your Average Stars", f"{round(avg_stars, 2)} / 5.0")
            col2.metric("Total Feedbacks Received", f"{len(df_teacher)} Students")

            st.subheader("📈 Performance Visualization Dashboard")
            v_col1, v_col2 = st.columns(2)

            with v_col1:
                st.markdown("#### 🌟 Star Distribution Trend")
                star_group = df_teacher.groupby('stars').agg(
                    Count=('stars', 'count'),
                    Students=('student_name', lambda x: ", ".join(x))
                ).reindex([1, 2, 3, 4, 5], fill_value=0).reset_index()

                fig_stars = px.bar(
                    star_group,
                    x='stars',
                    y='Count',
                    text='Count',
                    labels={'Count': 'Number of Students', 'stars': 'Rating Level', 'Students': 'Voted By'},
                    hover_data={'Students': True}
                )
                fig_stars.update_traces(textposition='outside')
                fig_stars.update_layout(yaxis_range=[0, max(star_group['Count']) + 2], height=280)
                st.plotly_chart(fig_stars, use_container_width=True)

            with v_col2:
                st.markdown("#### 🎭 Performance Categories Share")
                cat_group = df_teacher.groupby('performance').agg(
                    Count=('performance', 'count'),
                    Students=('student_name', lambda x: ", ".join(x))
                ).reset_index()

                fig_pie = px.pie(
                    cat_group,
                    values='Count',
                    names='performance',
                    color='performance',
                    labels={'Students': 'Students Group', 'performance': 'Category'},
                    color_discrete_map={'Good': '#2ca02c', 'Moderate': '#ff7f0e', 'Low': '#d62728'},
                    hover_data={'Students': True}
                )
                fig_pie.update_traces(textinfo='label+percent+value')
                fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=280, showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)

            st.markdown("---")
            st.subheader("📥 Export Evaluation Report")
            export_df = df_teacher[["student_name", "performance", "stars", "review"]].copy()
            export_df.columns = ["Student Name", "Performance Class", "Stars Rating", "Detailed Report Metrics Log"]
            csv_teacher_data = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download My Feedback Report (CSV)",
                data=csv_teacher_data,
                file_name=f"feedback_report_{user_info['username']}.csv",
                mime="text/csv",
                use_container_width=True
            )

            st.markdown("---")
            st.subheader("💡 What Students Say (For Your Improvement)")
            for idx, row in df_teacher.iterrows():
                with st.expander(f"Review by {row['student_name']} — Combined Rating: {row['performance']} | {'⭐' * int(row['stars'])}"):
                    st.write("**Detailed Ratings & Paragraph Review:**")
                    st.info(row['review'] if row['review'].strip() else "No specific parameter comments provided.")
