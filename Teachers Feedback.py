import streamlit as st, pandas as pd, plotly.express as px, mysql.connector
from mysql.connector import Error

st.set_page_config(page_title="Teacher Feedback Portal", layout="wide")
DB_CONFIG = {"host": st.secrets["mysql"]["host"], "user": st.secrets["mysql"]["user"], 
             "password": st.secrets["mysql"]["password"], "database": st.secrets["mysql"]["database"], 
             "port": int(st.secrets["mysql"]["port"]), "ssl_disabled": False}

@st.cache_resource
def get_db_connection(): return mysql.connector.connect(**DB_CONFIG)

def get_active_conn():
    conn = get_db_connection()
    if not conn.is_connected(): conn.reconnect(attempts=3, delay=1)
    return conn

def init_db():
    try:
        conn = get_active_conn(); cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (username VARCHAR(50) PRIMARY KEY, password VARCHAR(100) NOT NULL, role VARCHAR(20) NOT NULL, name VARCHAR(100) NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS feedback (id INT AUTO_INCREMENT PRIMARY KEY, teacher_id VARCHAR(50) NOT NULL, teacher_name VARCHAR(100) NOT NULL, student_name VARCHAR(100) NOT NULL, performance VARCHAR(20) NOT NULL, stars INT NOT NULL, review TEXT)")
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO users VALUES (%s, %s, %s, %s)", [
                ("admin", "admin123", "Admin", "System Admin"), ("T101", "teach123", "Teacher", "Dr. S.Uma"),
                ("T102", "teach123", "Teacher", "Prof. K. Arun"), ("T103", "teach123", "Teacher", "Dr. P.Anu"),
                ("T104", "teach123", "Teacher", "Prof. S.Senthil"), ("T105", "teach123", "Teacher", "Dr. K.Priya"),
                ("T106", "teach123", "Teacher", "Dr. S.Maheshwari")])
            conn.commit()
        cursor.close()
    except Error as e: st.error(f"DB Error: {e}")

if "db_initialized" not in st.session_state: init_db(); st.session_state.db_initialized = True

@st.cache_data(ttl=30)
def get_top_teacher():
    try:
        df = pd.read_sql("SELECT teacher_name, AVG(stars) as avg_stars FROM feedback GROUP BY teacher_id, teacher_name ORDER BY avg_stars DESC", get_active_conn())
        if df.empty: return "N/A", 0.0
        max_r = df["avg_stars"].max()
        return ", ".join(df[df["avg_stars"] == max_r]["teacher_name"].tolist()), round(max_r, 2)
    except: return "N/A", 0.0

st.title("🎓 Teacher Performance Feedback Portal")
top_name, top_rating = get_top_teacher()
st.info(f"🏆 **Top Ranked Teacher:** {top_name} | ⭐ **Avg Rating:** {top_rating}/5")
st.markdown("---")

if "logged_in_user" not in st.session_state: st.session_state.logged_in_user = None

if st.session_state.logged_in_user is None:
    with st.form("login_form"):
        col1, col2 = st.columns(2)
        with col1: username = st.text_input("User ID / Roll No")
        with col2: password = st.text_input("Password", type="password")
        if st.form_submit_button("Login securely to System", use_container_width=True):
            try:
                cursor = get_active_conn().cursor(dictionary=True)
                cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
                user_record = cursor.fetchone(); cursor.close()
                if user_record: st.session_state.logged_in_user = user_record; st.rerun()
                else: st.error("Invalid Credentials.")
            except Error as e: st.error(f"Login Error: {e}")
else:
    user_info = st.session_state.logged_in_user
    st.sidebar.markdown(f"### Welcome, **{user_info['name']}**\n**Role:** `{user_info['role']}`")
    if st.sidebar.button("Logout", use_container_width=True): st.session_state.logged_in_user = None; st.rerun()

    if user_info["role"] == "Admin":
        st.header("🛠️ Admin Console")
        try: df_all = pd.read_sql("SELECT * FROM feedback", get_active_conn())
        except: df_all = pd.DataFrame()
        
        if not df_all.empty:
            ranking = df_all.groupby("teacher_id").agg(
                teacher_name=("teacher_name", "first"), 
                avg_stars=("stars", "mean"), 
                total_reviews=("stars", "count"),
                voted_by=("student_name", lambda x: ", ".join(x.unique()))
            ).reset_index().sort_values(by="avg_stars", ascending=False)
            
            ranking["avg_stars"] = ranking["avg_stars"].round(2)
            ranking["leaderboard_rank"] = ranking["avg_stars"].rank(ascending=False, method="min").astype(int)
            ranking = ranking.sort_values(by="leaderboard_rank")

            fig_ranking = px.bar(
                ranking, 
                x="teacher_name", 
                y="avg_stars", 
                title="Faculty Rankings & Performance Details", 
                color="avg_stars", 
                color_continuous_scale="turbo",
                labels={
                    "teacher_name": "Faculty Member Name", 
                    "avg_stars": "Average Rating Score", 
                    "leaderboard_rank": "Leaderboard Rank", 
                    "total_reviews": "Total Students Voted", 
                    "voted_by": "Voted By"
                },
                hover_data=["leaderboard_rank", "total_reviews", "voted_by"]
            )
            st.plotly_chart(fig_ranking, use_container_width=True)

        st.markdown("### 📥 Export Institutional Insights Data")
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            try:
                master_csv = df_all.to_csv(index=False).encode('utf-8') if not df_all.empty else b""
                st.download_button(
                    label="📥 Download Master Feedback Log (CSV)",
                    data=master_csv,
                    file_name="master_feedback_log.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            except Exception as e: st.error(f"Error: {e}")
        with exp_col2:
            try:
                agg_csv = ranking.to_csv(index=False).encode('utf-8') if 'ranking' in locals() and not ranking.empty else b""
                st.download_button(
                    label="📥 Download Aggregated Performance Report (CSV)",
                    data=agg_csv,
                    file_name="aggregated_performance_report.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            except Exception as e: st.error(f"Error: {e}")
        st.markdown("---")
            
        c1, c2 = st.columns(2)
        with c1:
            with st.form("add_user", clear_on_submit=True):
                st.subheader("➕ Onboard User")
                uid, name, pwd, role = st.text_input("ID"), st.text_input("Name"), st.text_input("Password", type="password"), st.selectbox("Role", ["Student", "Teacher"])
                if st.form_submit_button("Save User"):
                    if uid and name and pwd:
                        try:
                            conn = get_active_conn(); cur = conn.cursor()
                            cur.execute("INSERT INTO users VALUES (%s, %s, %s, %s)", (uid, pwd, role, name))
                            conn.commit(); cur.close()
                            st.success("User added successfully!")
                            st.rerun()
                        except Error as e: st.error(f"Error: {e}")
                    else: st.warning("Please fill all fields.")
                    
        with c2:
            with st.form("delete_user_form"):
                st.subheader("🗑️ Delete User ID")
                try:
                    df_users_all = pd.read_sql("SELECT username, name, role FROM users WHERE username != 'admin'", get_active_conn())
                    user_list = df_users_all['username'].tolist() if not df_users_all.empty else []
                except: user_list = []
                
                del_uid = st.selectbox("Select User ID to Remove", user_list) if user_list else st.selectbox("No users available", [""])
                if st.form_submit_button("Delete User"):
                    if del_uid and del_uid != "":
                        try:
                            conn = get_active_conn(); cur = conn.cursor()
                            cur.execute("DELETE FROM users WHERE username = %s", (del_uid,))
                            conn.commit(); cur.close()
                            st.success(f"User {del_uid} deleted successfully!")
                            st.rerun()
                        except Error as e: st.error(f"Error: {e}")

        st.markdown("---")
        st.subheader("📋 Categorized Users Directory")
        try:
            df_dir = pd.read_sql("SELECT username as `ID`, name as `Name`, role as `Role` FROM users", get_active_conn())
            if not df_dir.empty:
                tab_t, tab_s = st.tabs(["👩‍🏫 Teachers Directory", "👨‍🎓 Students Directory"])
                with tab_t:
                    teachers_df = df_dir[df_dir["Role"] == "Teacher"]
                    st.dataframe(teachers_df, use_container_width=True, hide_index=True)
                with tab_s:
                    students_df = df_dir[df_dir["Role"] == "Student"]
                    st.dataframe(students_df, use_container_width=True, hide_index=True)
        except Exception as e: st.error(f"Could not load directory: {e}")

    elif user_info["role"] == "Student":
        st.header("📝 Submit Comprehensive Teacher Feedback")
        st.markdown("Please evaluate your teachers across key academic parameters. Submissions are categorized into **Good**, **Moderate**, or **Low** performance.")
        
        try:
            cursor = get_active_conn().cursor(dictionary=True)
            cursor.execute("SELECT username, name FROM users WHERE role = 'Teacher'")
            teachers = {row["username"]: row["name"] for row in cursor.fetchall()}; cursor.close()
        except: teachers = {}

        if teachers:
            with st.form("feedback_form", clear_on_submit=True):
                tid = st.selectbox("Select Faculty Member", list(teachers.keys()), format_func=lambda x: f"{teachers[x]} ({x})")
                
                st.markdown("#### Performance Metrics (5 = Excellent, 1 = Poor)")
                mc1, mc2 = st.columns(2)
                with mc1: 
                    ml = st.selectbox("Lecturing Quality", [5,4,3,2,1], index=0)
                    md = st.selectbox("Classroom Discipline", [5,4,3,2,1], index=0)
                    mp = st.selectbox("Portion Coverage", [5,4,3,2,1], index=0)
                with mc2: 
                    mi = st.selectbox("Overall Impression", [5,4,3,2,1], index=0)
                    mc = st.selectbox("Student Communication", [5,4,3,2,1], index=0)
                
                rev = st.text_area("Additional Comments / Suggestions")
                
                if st.form_submit_button("Submit Evaluative Feedback", use_container_width=True):
                    avg = (ml + md + mp + mi + mc) / 5
                    # Automatic classification into Good / Moderate / Low
                    if avg >= 4.0:
                        perf = "Good"
                    elif avg >= 2.5:
                        perf = "Moderate"
                    else:
                        perf = "Low"
                        
                    conn = get_active_conn(); cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO feedback (teacher_id, teacher_name, student_name, performance, stars, review) VALUES (%s, %s, %s, %s, %s, %s)",
                        (tid, teachers[tid], user_info["name"], perf, round(avg), f"[Lecturing:{ml}, Discipline:{md}, Portion:{mp}, Impression:{mi}, Communication:{mc}] Review: {rev}")
                    )
                    conn.commit(); cur.close()
                    st.success(f"Feedback submitted successfully! Classified as: **{perf}** (Average Rating: {round(avg, 2)} ⭐)")
                    st.rerun()

    elif user_info["role"] == "Teacher":
        st.header(f"📊 Performance Insights: {user_info['name']}")
        try: df_teacher = pd.read_sql("SELECT * FROM feedback WHERE teacher_name = %s", get_active_conn(), params=(user_info["name"],))
        except: df_teacher = pd.DataFrame()

        if not df_teacher.empty:
            st.metric("Overall Average Rating", f"{round(df_teacher['stars'].mean(), 2)} / 5.0")
            v_col1, v_col2 = st.columns(2)
            
            with v_col1:
                st.markdown("#### 🌟 Star Distribution & Student Count")
                star_group = df_teacher.groupby('stars').agg(
                    Count=('stars', 'count'),
                    Students=('student_name', lambda x: ", ".join(x))
                ).reset_index()
                
                full_stars = pd.DataFrame({'stars': [1, 2, 3, 4, 5]})
                star_group = pd.merge(full_stars, star_group, on='stars', how='left').fillna(0)

                fig_stars = px.bar(
                    star_group,
                    x='stars',
                    y='Count',
                    text='Count',
                    labels={'Count': 'Number of Students', 'stars': 'Rating Level', 'Students': 'Voted By'},
                    hover_data={'Students': True}
                )
                fig_stars.update_traces(textposition='outside')
                max_count = int(star_group['Count'].max()) if not star_group.empty else 5
                fig_stars.update_layout(yaxis_range=[0, max_count + 2], height=280)
                st.plotly_chart(fig_stars, use_container_width=True)

            with v_col2:
                st.markdown("#### 🥧 Performance Category Breakdown")
                cat_group = df_teacher.groupby('performance').agg(Count=('performance', 'count')).reset_index()
                fig_pie = px.pie(cat_group, values='Count', names='performance', height=280)
                st.plotly_chart(fig_pie, use_container_width=True)
                
            st.markdown("---")
            st.subheader("📋 Student Feedback Records")
            st.dataframe(df_teacher[["student_name", "performance", "stars", "review"]], use_container_width=True, hide_index=True)
        else: 
            st.info("No feedback received yet.")
