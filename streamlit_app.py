import os
import re
import csv
import io
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="TalentFlow Recruiter Hub",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JD_DIR = os.path.join(BASE_DIR, "ACTIVE_JDS")
DB_PATH = os.path.join(BASE_DIR, "candidate_vault.db")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(JD_DIR, exist_ok=True)

# ----------------- Database / Vault Lockout -----------------
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_name TEXT,
                client_name TEXT,
                recruiter_name TEXT,
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                lock_expires_at DATETIME
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.warning(f"DB warning: {e}")

init_db()

def check_vault_lockout(name, client):
    if not os.path.exists(DB_PATH) or not name:
        return False, None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        clean = re.sub(r'[^a-zA-Z\s]', '', name).strip()
        if len(clean) < 4:
            conn.close()
            return False, None
        cur.execute("""
            SELECT client_name, lock_expires_at 
            FROM client_submissions 
            WHERE candidate_name LIKE ? AND (lock_expires_at > CURRENT_TIMESTAMP OR lock_expires_at IS NULL)
        """, (f"%{clean}%",))
        row = cur.fetchone()
        conn.close()
        if row:
            return True, row[0]
        return False, None
    except Exception:
        return False, None

def mark_candidate_submitted(candidate_name, client_name, recruiter_name):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO client_submissions (candidate_name, client_name, recruiter_name, lock_expires_at)
            VALUES (?, ?, ?, datetime('now', '+30 days'))
        """, (candidate_name, client_name, recruiter_name))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Failed to submit: {e}")
        return False

# ----------------- JD Functions -----------------
def get_available_jds():
    if not os.path.exists(JD_DIR):
        return []
    files = [f for f in os.listdir(JD_DIR) if f.endswith(".txt")]
    priority = [
        "1_LTIMindtree_Salesforce_CPQ.txt",
        "2_Capgemini_Java_Fullstack.txt",
        "3_TechMahindra_DataEngineer.txt"
    ]
    ordered = [p for p in priority if p in files]
    remaining = sorted([f for f in files if f not in priority])
    result = []
    for f in ordered + remaining:
        title = f.replace(".txt", "").replace("_", " ")
        result.append({"filename": f, "title": title})
    return result

def parse_jd(filename):
    path = os.path.join(JD_DIR, filename)
    client = "LTIMINDTREE"
    min_exp, max_exp = 4.0, 10.0
    skills = ["Salesforce", "CPQ", "Conga", "Apex", "Lightning"]
    if not os.path.exists(path):
        return {"client": client, "min_exp": min_exp, "max_exp": max_exp, "skills": skills}

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    m_client = re.search(r"Target Client\s*:\s*([^\n\r]+)", text, re.I)
    if m_client:
        client = m_client.group(1).strip().upper()

    m_exp = re.search(r"Experience\s*:\s*(\d+)\s*(?:-|to)\s*(\d+)", text, re.I)
    if m_exp:
        min_exp, max_exp = float(m_exp.group(1)), float(m_exp.group(2))

    extracted_skills = []
    m_skills = re.search(r"Mandatory Skills\s*:\s*([^\n\r]+)", text, re.I)
    if m_skills:
        extracted_skills.extend([s.strip() for s in m_skills.group(1).split(",") if s.strip()])

    m_sec = re.search(r"Secondary Skills\s*:\s*([^\n\r]+)", text, re.I)
    if m_sec:
        extracted_skills.extend([s.strip() for s in m_sec.group(1).split(",") if s.strip()])

    if extracted_skills:
        seen = set()
        skills = [s for s in extracted_skills if not (s.lower() in seen or seen.add(s.lower()))]

    return {
        "client": client,
        "min_exp": min_exp,
        "max_exp": max_exp,
        "skills": skills
    }

# ----------------- Candidate Screening Logic -----------------
def screen_candidates(jd_filename, min_score, fresh_only):
    jd = parse_jd(jd_filename)
    latest_file = os.path.join(UPLOADS_DIR, "latest_candidates.csv")
    default_seed = os.path.join(BASE_DIR, "default_candidates.csv")
    
    file_to_read = None
    if os.path.exists(latest_file):
        file_to_read = latest_file
    elif os.path.exists(default_seed):
        file_to_read = default_seed

    if not file_to_read:
        return []

    candidates = []
    with open(file_to_read, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)
        fn_map = {k.strip().lower(): k for k in (reader.fieldnames or []) if k}

        def get_val(row_dict, *keys):
            for k in keys:
                actual = fn_map.get(k.lower())
                if actual and row_dict.get(actual):
                    return row_dict[actual].strip()
                if k in row_dict and row_dict[k]:
                    return row_dict[k].strip()
            return ""

        for row in reader:
            name = get_val(row, "Name", "Candidate Name", "Candidate", "Full Name")
            if not name:
                continue

            role = get_val(row, "Current_Role", "Current Role", "Current_Role_Company", "Role", "Designation", "Job Title")
            exp = get_val(row, "Experience", "Total Experience", "Exp", "Work Experience")
            loc = get_val(row, "Location", "Current Location", "City")
            skills_raw = get_val(row, "All_Skills", "Key_Skills", "Key Skills", "Skills", "Matched_Skills", "Matched_JD_Skills", "Skillset")
            notice = get_val(row, "Notice_Period", "Notice Period", "Notice")
            phone_col = get_val(row, "Phone", "Mobile", "Contact", "Discovered_Phone", "Phone_Number")
            email_col = get_val(row, "Email", "Mail", "Email_Address", "Discovered_Email")
            comp_col = get_val(row, "Company", "Current_Company", "Organization", "Employer")

            exp_years = 0.0
            m = re.search(r"(\d+)y\s*(\d*)m?", exp, re.I)
            if m:
                exp_years = round(int(m.group(1)) + (int(m.group(2) or 0) / 12.0), 1)

            full_text = f"{name} {role} {skills_raw}".lower()
            matched = [s for s in jd["skills"] if re.search(r"\b" + re.escape(s.lower()) + r"\b", full_text)]
            skill_score = int((len(matched) / max(len(jd["skills"]), 1)) * 60)

            if jd["min_exp"] <= exp_years <= jd["max_exp"]:
                exp_score = 40
            elif abs(exp_years - jd["min_exp"]) <= 2 or abs(exp_years - jd["max_exp"]) <= 2:
                exp_score = 25
            else:
                exp_score = 10

            total_score = min(skill_score + exp_score, 100)

            if total_score < min_score:
                continue

            is_locked, locked_client = check_vault_lockout(name, jd["client"])
            if fresh_only and is_locked:
                continue

            candidates.append({
                "name": name,
                "role": role or "Candidate",
                "company": comp_col or "Not Specified",
                "experience": f"{exp_years} yrs" if exp_years > 0 else exp,
                "location": loc or "India",
                "notice": notice or "Immediate",
                "score": total_score,
                "matched_skills": ", ".join(matched) if matched else "General Fit",
                "locked": is_locked,
                "locked_client": locked_client or "",
                "phone": phone_col or "Available",
                "email": email_col or "Available",
                "portal_url": get_val(row, "Portal_URL", "Profile_URL", "URL")
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates

# ----------------- UI Sidebar -----------------
st.sidebar.title("🎯 TalentFlow Control")

jds = get_available_jds()
jd_options = {j["title"]: j["filename"] for j in jds}

if not jd_options:
    st.sidebar.error("No Job Descriptions found.")
    st.stop()

selected_jd_title = st.sidebar.selectbox("1. Select Job Role (JD)", list(jd_options.keys()))
selected_jd_file = jd_options[selected_jd_title]

# Score Threshold
min_score = st.sidebar.selectbox(
    "2. Match Threshold",
    options=[50, 80, 90, 70, 0],
    format_func=lambda x: {
        50: "50% to 100% (Recommended Matches)",
        80: "80% to 100% (Strict Best Matches)",
        90: "90% to 100% (Top Tier Only)",
        70: "70% to 100% (High Matches)",
        0: "All Scores (0% - 100%)"
    }[x]
)

fresh_only = st.sidebar.checkbox("Fresh Candidates Only (Exclude Lockouts)", value=True)

st.sidebar.markdown("---")

# CSV Uploader
st.sidebar.subheader("📤 Upload Candidate CSV")
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
if uploaded_file is not None:
    dest_path = os.path.join(UPLOADS_DIR, "latest_candidates.csv")
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.sidebar.success(f"Saved: {uploaded_file.name}")

st.sidebar.markdown("---")

# Add New Role
with st.sidebar.expander("➕ Add New Job Role"):
    with st.form("create_jd_form"):
        new_client = st.text_input("Client Name", placeholder="e.g. INFOSYS")
        new_role = st.text_input("Role Title", placeholder="e.g. AWS Cloud Engineer")
        c1, c2 = st.columns(2)
        new_min_exp = c1.text_input("Min Exp", value="3")
        new_max_exp = c2.text_input("Max Exp", value="8")
        new_skills = st.text_area("Mandatory Skills (comma-separated)", placeholder="AWS, Terraform, Python, Docker")
        submitted = st.form_submit_button("Create Role")
        if submitted:
            if new_client and new_role and new_skills:
                safe_title = re.sub(r'[^a-zA-Z0-9_]', '_', f"{new_client}_{new_role}").strip('_')
                filepath = os.path.join(JD_DIR, f"{safe_title}.txt")
                content = f"""Target Client: {new_client}\nRole: {new_role}\nExperience: {new_min_exp} to {new_max_exp} Years\nMandatory Skills: {new_skills}\nNotice Period: Immediate to 30 Days\n"""
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                st.success("New role added!")
                st.rerun()
            else:
                st.error("Please fill all required fields.")

# Delete Role
with st.sidebar.expander("🗑️ Delete Selected Role"):
    st.write(f"Delete: **{selected_jd_title}**?")
    if st.button("Confirm Delete", type="primary"):
        target_path = os.path.join(JD_DIR, selected_jd_file)
        if os.path.exists(target_path):
            os.remove(target_path)
            st.success("Role deleted successfully!")
            st.rerun()

# ----------------- Main View -----------------
jd_info = parse_jd(selected_jd_file)

st.title(f"🚀 TalentFlow: {selected_jd_title}")
st.caption(f"Target Client: **{jd_info['client']}** | Experience: **{jd_info['min_exp']} - {jd_info['max_exp']} yrs** | Mandatory Skills: **{', '.join(jd_info['skills'])}**")

candidates = screen_candidates(selected_jd_file, min_score, fresh_only)

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Screened Candidates", len(candidates))
top_tier_count = sum(1 for c in candidates if c["score"] >= 80)
col2.metric("Top Matches (≥80%)", top_tier_count)
locked_count = sum(1 for c in candidates if c["locked"])
col3.metric("Lockout Shield", f"{len(candidates) - locked_count} Fresh")

st.markdown("---")

if not candidates:
    st.info(f"0 candidates found at {min_score}% threshold. Try lowering the threshold from the sidebar or uploading a new CSV.")
else:
    df = pd.DataFrame(candidates)
    
    # Custom display format
    display_df = df[["score", "name", "role", "company", "experience", "location", "notice", "matched_skills"]].copy()
    display_df.columns = ["Score (%)", "Candidate Name", "Role", "Company", "Experience", "Location", "Notice", "Matched Skills"]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score (%)": st.column_config.ProgressColumn(
                "Match Score",
                format="%d%%",
                min_value=0,
                max_value=100
            )
        }
    )

    # Submission / Lockout Section
    st.subheader("🔒 Client Submission & Duplicate Lockout")
    recruiter_name = st.text_input("Your Recruiter Name", value="Recruiter")
    candidate_names = [c["name"] for c in candidates if not c["locked"]]
    
    if candidate_names:
        selected_candidate = st.selectbox("Select Candidate to Lock for Client", candidate_names)
        if st.button(f"Submit & Lock {selected_candidate} for {jd_info['client']}"):
            if mark_candidate_submitted(selected_candidate, jd_info["client"], recruiter_name):
                st.success(f"Candidate {selected_candidate} is now LOCKED for {jd_info['client']} for 30 days!")
                st.rerun()
    else:
        st.write("All listed candidates are currently locked or no eligible candidates found.")
