import streamlit as st, pandas as pd, plotly.express as px, mysql.connector
from mysql.connector import Error

st.set_page_config(page_title="Teacher Feedback Portal", layout="wide")

try:
    DB_CONFIG = {
        "host": st.secrets["mysql"]["host"], 
        "user": st.secrets["mysql"]["user"], 
        "password": st.secrets["mysql"]["password"], 
        "database": st.secrets["mysql"]["database"], 
        "port": int(st.secrets["mysql"]["port"]), 
        "ssl_disabled": False
    }
except Exception:
    DB_CONFIG = None

@st.cache_resource
def get_db_connection(): 
    if not DB_CONFIG: return None
    return mysql.connector.connect(**DB_CONFIG)

def get_active_conn():
    try:
        conn = get_db_connection()
        if not conn: return None
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=1)
        else:
            conn.ping(reconnect=True, attempts=3, delay=1)
        return conn
    except Exception:
        st.cache_resource.clear()
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except:
            return None

def init_db():
    try:
        conn = get_active_conn()
        if not conn: return
        cursor = conn.cursor()
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
    except Error as e: 
        st.error(f"Database Initialization Error: {e}")

if "db_initialized" not in st.session_state: 
    init_db() 
    st.session_state.db_initialized = True

@st.cache_data(ttl=30)
def get_top_teacher():
    try:
        conn = get_active_conn()
        if not conn: return "N/A", 0.0
        df = pd.read_sql("SELECT teacher_name, AVG(stars) as avg_stars FROM feedback GROUP BY teacher_id, teacher_name ORDER BY avg_stars DESC", conn)
        if df.empty: return "N/A", 0.0
        max_r = df["avg_stars"].max()
        return ", ".join(df[df["avg_stars"] == max_r]["teacher_name"].tolist()), round(max_r, 2)
    except: 
        return "N/A", 0.0

st.title("🎓 Teacher Performance Feedback Portal")
top_name, top_rating = get_top_teacher()
st.info(f"🏆 **Top Ranked Teacher:** {top_name} | ⭐ **Avg Rating:** {top_rating}/5")
st.markdown("---")

if "logged_in_user" not in st.session_state: 
    st.session_state.logged_in_user = None

if st.session_state.logged_in_user is None:
    with st.form("login_form"):
        col1, col2 = st.columns(2)
        with col1: username = st.text_input("User ID / Roll No")
        with col2: password = st.text_input("Password", type="password")
        if st.form_submit_button("Login securely to System", use_container_width=True):
            try:
                conn = get_active_conn()
                if not conn:
                    st.error("Database connection failed. Please check your secrets configuration.")
                else:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
                    user_record = cursor.fetchone()
                    cursor.close()
                    if user_record: 
                        st.session_state.logged_in_user = user_record
                        st.rerun()
                    else: 
                        st.error("Invalid Credentials.")
            except Error as e: 
                st.error(f"Login Error: {e}")
else:
    user_info = st.session_state.logged_in_user
    st.sidebar.markdown(f"### Welcome, **{user_info['name']}**\n**Role:** `{user_info['role']}`")
    if st.sidebar.button("Logout", use_container_width=True): 
        st.session_state.logged_in_user = None
        st.rerun()

    if user_info["role"] == "Admin":
        st.header("🛠️ Admin Console")
        try: 
            df_all = pd.read_sql("SELECT * FROM feedback", get_active_conn())
        except: 
            df_all = pd.DataFrame()
        
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
            
            ranking["rating_display"] = ranking["avg_stars"].astype(str) + " ⭐"

            fig_ranking = px.bar(
                ranking, 
                x="teacher_name", 
                y="avg_stars", 
                text="rating_display",
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
            fig_ranking.update_traces(textposition='outside')
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
                            conn = get_active_conn()
                            cur = conn.cursor()
                            cur.execute("INSERT INTO users VALUES (%s, %s, %s, %s)", (uid, pwd, role, name))
                            conn.commit()
                            cur.close()
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
                            conn = get_active_conn()
                            cur = conn.cursor()
                            cur.execute("DELETE FROM users WHERE username = %s", (del_uid,))
                            conn.commit()
                            cur.close()
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
        st.header("📝 Submit Teacher Feedback")
        try:
            conn = get_active_conn()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT username, name FROM users WHERE role = 'Teacher'")
            teachers = {row["username"]: row["name"] for row in cursor.fetchall()}
            cursor.close()
        except: 
            teachers = {}

        if teachers:
            with st.form("feedback_form", clear_on_submit=True):
                tid = st.selectbox("Select Faculty Member", list(teachers.keys()), format_func=lambda x: f"{teachers[x]} ({x})")
                
                st.markdown("### 📊 Performance Assessment Matrix")
                st.markdown("Please evaluate your instructor honestly across the following indicators:")
                
                mc1, mc2 = st.columns(2)
                with mc1: 
                    ml = st.selectbox("Lecturing Quality & Explanation", [5, 4, 3, 2, 1], index=0)
                    md = st.selectbox("Maintaining Discipline & Classroom Control", [5, 4, 3, 2, 1], index=0)
                    mp = st.selectbox("Completing Portion & Syllabus Schedule", [5, 4, 3, 2, 1], index=0)
                with mc2: 
                    mi = st.selectbox("General Impression Between Students", [5, 4, 3, 2, 1], index=0)
                    mc = st.selectbox("Communication Skills & Approachability", [5, 4, 3, 2, 1], index=0)
                
                st.markdown("---")
                st.markdown("**Overall Score Star Selection (Optional override link):**")
                
                star_selection = st.feedback("stars", key="overall_stars_widget")
                
                st.markdown("**Paragraph Review / Detailed Comments**")
                rev = st.text_area("Provide instructional feedback here regarding lessons...")
                
                if st.form_submit_button("Submit"):
                    calc_avg = (ml + md + mp + mi + mc) / 5
                    
                    if star_selection is not None:
                        override_star = int(star_selection) + 1
                        final_stars = override_star
                    else:
                        final_stars = round(calc_avg)
                    
                    if final_stars >= 4:
                        perf = "Good"
                    elif final_stars >= 3:
                        perf = "Moderate"
                    else:
                        perf = "Low"
                        
                    detailed_review_text = f"[Lecturing: {ml}/5, Discipline: {md}/5, Portion: {mp}/5, Impression: {mi}/5, Communication: {mc}/5] {rev}"
                    
                    conn = get_active_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO feedback (teacher_id, teacher_name, student_name, performance, stars, review) VALUES (%s, %s, %s, %s, %s, %s)",
                        (tid, teachers[tid], user_info["name"], perf, final_stars, detailed_review_text)
                    )
                    conn.commit()
                    cur.close()
                    st.success("Feedback submitted successfully!")
                    st.rerun()

        st.markdown("---")
        st.subheader("📊 Your Feedback History")
        try:
            df_my_feedback = pd.read_sql(
                "SELECT teacher_id as `Teacher ID`, teacher_name as `Teacher Name`, performance as `Classification`, stars as `Stars Given`, review as `Your Logged Review Metrics` FROM feedback WHERE student_name = %s",
                get_active_conn(), params=(user_info["name"],)
            )
            if not df_my_feedback.empty:
                st.dataframe(df_my_feedback, use_container_width=True, hide_index=True)
                csv_data = df_my_feedback.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download My Submission History (CSV)",
                    data=csv_data,
                    file_name="my_submission_history.csv",
                    mime="text/csv"
                )
            else:
                st.info("You haven't submitted any feedback yet.")
        except Exception as e:
            st.error(f"Could not load your history: {e}")

    elif user_info["role"] == "Teacher":
        st.header(f"📊 Performance Insights: {user_info['name']}")
        try: 
            df_teacher = pd.read_sql("SELECT * FROM feedback WHERE teacher_name = %s", get_active_conn(), params=(user_info["name"],))
        except: 
            df_teacher = pd.DataFrame()

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
