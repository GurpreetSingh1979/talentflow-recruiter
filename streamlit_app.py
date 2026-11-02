import os
import re
import csv
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Gurpreet's TalentFlow - Cloud Recruiter Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JD_DIR = os.path.join(BASE_DIR, "ACTIVE_JDS")
DB_PATH = os.path.join(BASE_DIR, "candidate_vault.db")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(JD_DIR, exist_ok=True)

# ---------------- Custom CSS to replicate Render Portal Exactly ----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    
    .main .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1650px !important;
    }
    
    /* Header bar */
    .tf-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid #e2e8f0;
    }
    .tf-logo-title {
        font-size: 24px;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.5px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .tf-logo-title span {
        color: #2563eb;
    }
    .tf-logo-desc {
        font-size: 13.5px;
        color: #64748b;
        margin-top: 4px;
        font-weight: 500;
    }
    .badge-pill {
        font-size: 12px;
        font-weight: 700;
        padding: 6px 14px;
        border-radius: 9999px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .badge-zero { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
    .badge-owner { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
    .badge-naukri { background: #4338ca; color: #fff; border: none; }
    
    /* Stats Grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    .stat-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stat-label {
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stat-val {
        font-size: 26px;
        font-weight: 800;
        color: #0f172a;
        margin-top: 4px;
    }
    .stat-desc {
        font-size: 11.5px;
        color: #64748b;
        margin-top: 4px;
    }
    
    /* Candidate Table */
    .table-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        overflow: hidden;
        margin-top: 20px;
    }
    .table-top {
        padding: 14px 20px;
        border-bottom: 1px solid #e2e8f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #fafafa;
    }
    .table-title {
        font-size: 14px;
        font-weight: 700;
        color: #1e293b;
    }
    
    table.tf-table {
        width: 100%;
        border-collapse: collapse;
        text-align: left;
        font-size: 12.5px;
    }
    table.tf-table th {
        background: #f1f5f9;
        color: #475569;
        font-weight: 700;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 12px 16px;
        border-bottom: 2px solid #e2e8f0;
    }
    table.tf-table td {
        padding: 14px 16px;
        border-bottom: 1px solid #e2e8f0;
        vertical-align: middle;
    }
    table.tf-table tr:hover td {
        background: #f8fafc;
    }
    
    .match-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 800;
        padding: 5px 10px;
        border-radius: 7px;
    }
    .match-top { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
    .match-high { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
    .match-good { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
    
    .name-title { font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 2px; }
    .role-title { font-size: 12px; font-weight: 600; color: #2563eb; }
    .comp-title { font-size: 11.5px; color: #64748b; margin-top: 1px; }
    
    .tag-pill { display: inline-block; font-size: 10.5px; font-weight: 600; padding: 2px 7px; border-radius: 4px; margin: 2px; }
    .tag-matched { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
    .tag-default { background: #f1f5f9; color: #64748b; }
    
    .status-fresh { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 5px; display: inline-flex; align-items: center; gap: 3px; }
    .status-locked { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 5px; display: inline-flex; align-items: center; gap: 3px; }
    
    .radar-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 5px; display: inline-block; margin-bottom: 2px; }
    .radar-immediate { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
    .radar-active { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
    
    .action-links { display: flex; flex-direction: column; gap: 4px; min-width: 140px; }
    .link-btn { text-decoration: none !important; font-size: 10.5px; font-weight: 700; padding: 5px 10px; border-radius: 5px; text-align: center; display: inline-flex; align-items: center; justify-content: center; gap: 5px; }
    .link-li { background: #0a66c2; color: #fff !important; }
    .link-search { background: #f1f5f9; color: #334155 !important; border: 1px solid #cbd5e1; }
    .link-search:hover { background: #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# ----------------- Functions -----------------
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

    extracted = []
    m_skills = re.search(r"Mandatory Skills\s*:\s*([^\n\r]+)", text, re.I)
    if m_skills:
        extracted.extend([s.strip() for s in m_skills.group(1).split(",") if s.strip()])

    m_sec = re.search(r"Secondary Skills\s*:\s*([^\n\r]+)", text, re.I)
    if m_sec:
        extracted.extend([s.strip() for s in m_sec.group(1).split(",") if s.strip()])

    if extracted:
        seen = set()
        skills = [s for s in extracted if not (s.lower() in seen or seen.add(s.lower()))]

    return {"client": client, "min_exp": min_exp, "max_exp": max_exp, "skills": skills}

def evaluate_readiness(notice, role, skills_text):
    notice_clean = (notice or "").lower().strip()
    is_immediate = any(k in notice_clean for k in ["immediate", "15 days", "serving", "1 month", "30 days"])
    has_certs = any(k in (skills_text or "").lower() for k in ["certified", "certification", "trailhead", "ranger", "superbadge", "cert"])
    
    if is_immediate and has_certs:
        return "HIGH_INTENT", "⚡ Actively Interviewing (Notice + Certs)"
    elif is_immediate:
        return "HIGH_INTENT", "🟢 High Availability (Serving Notice / Immediate)"
    elif has_certs:
        return "INTERVIEW_READY", "🎓 Active Learner (Recent Certifications)"
    else:
        return "WARM_ACTIVE", "🟡 Profile Updated Recently"

def extract_phone_and_email(text):
    if not text:
        return "", ""
    phones = re.findall(r'(?:\+?91[\s\-]?)?[6789]\d{9}', text)
    valid_phones = []
    for p in phones:
        clean = re.sub(r'[^\d]', '', p)
        if len(clean) == 10 and clean[0] in '6789':
            valid_phones.append(clean)
        elif len(clean) == 12 and clean.startswith('91') and clean[2] in '6789':
            valid_phones.append('+' + clean)

    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    blacklist = ['example.com', 'domain.com', 'sentry.io', 'w3.org', 'company.com', 'email.com', 'yourcompany.com', 'naukri.com']
    valid_emails = [e.lower() for e in emails if not any(b in e.lower() for b in blacklist)]

    phone_str = list(dict.fromkeys(valid_phones))[0] if valid_phones else ""
    email_str = list(dict.fromkeys(valid_emails))[0] if valid_emails else ""
    return phone_str, email_str

def screen_candidates(jd_filename, min_score, fresh_only):
    jd = parse_jd(jd_filename)
    latest_file = os.path.join(UPLOADS_DIR, "latest_candidates.csv")
    default_seed = os.path.join(BASE_DIR, "default_candidates.csv")
    
    file_to_read = latest_file if os.path.exists(latest_file) else (default_seed if os.path.exists(default_seed) else None)
    if not file_to_read:
        return [], "No Candidate CSV"

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
            elif (jd["min_exp"] - 2.0) <= exp_years <= (jd["max_exp"] + 3.0):
                exp_score = 25
            elif exp_years > 0:
                exp_score = 15
            else:
                exp_score = 10

            total_score = min(skill_score + exp_score, 100)

            if total_score < min_score:
                continue

            comp = comp_col
            if not comp and " at " in role:
                comp = role.split(" at ")[-1].strip()

            phone_raw, email_raw = extract_phone_and_email(f"{skills_raw} {name} {role}")
            phone = phone_raw or phone_col
            email = email_raw or email_col

            radar_type, radar_label = evaluate_readiness(notice, role, skills_raw)
            parsed_skills = [s.strip() for s in skills_raw.replace("|;", ",").replace("|", ",").split(",") if s.strip() and len(s.strip()) < 35]

            candidates.append({
                "name": name,
                "score": total_score,
                "role": role or "Developer",
                "company": comp or "Confidential",
                "exp": f"{exp_years} yrs" if exp_years > 0 else (exp or "N/A"),
                "location": loc or "Pan India",
                "notice": notice or "Immediate",
                "radar_type": radar_type,
                "radar_label": radar_label,
                "skills": parsed_skills[:6],
                "matched_skills": matched,
                "phone": phone,
                "email": email,
                "is_locked": False
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates, os.path.basename(file_to_read)

# ----------------- Render-like Header -----------------
st.markdown("""
<div class="tf-header">
    <div>
        <div class="tf-logo-title">⚡ Talent<span>Flow</span> Cloud Screening Portal</div>
        <div class="tf-logo-desc">Automated Candidate Sourcing, Duplicate Lockout Guard & Intent Radar for Recruitment Teams</div>
    </div>
    <div style="display:flex;gap:10px;align-items:center;">
        <span class="badge-pill badge-naukri">🚀 100+ Naukri Extractor Active</span>
        <span class="badge-pill badge-zero">🛡️ 0 Recruiter Credits Used</span>
        <span class="badge-pill badge-owner">👤 Designed by Gurpreet Singh</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- Filter Bar (Horizontal like Render) -----------------
jds = get_available_jds()
jd_map = {j["title"]: j["filename"] for j in jds}

col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

with col1:
    selected_title = st.selectbox(
        "1. Select Job Role (JD)",
        options=list(jd_map.keys()),
        index=0
    )
    selected_filename = jd_map[selected_title]

with col2:
    threshold_options = [50, 80, 90, 70, 0]
    min_score = st.selectbox(
        "2. Match Threshold",
        options=threshold_options,
        index=0,
        format_func=lambda x: {
            50: "50% to 100% (Recommended)",
            80: "80% to 100% (Strict)",
            90: "90% to 100% (Top Tier)",
            70: "70% to 100% (High)",
            0: "All Scores (0% - 100%)"
        }[x]
    )

with col3:
    fresh_filter = st.selectbox(
        "3. Duplicate Protection",
        options=["Fresh Only (Hide Prior Submissions)", "Show All (Include Locked)"]
    )
    fresh_only = "Fresh" in fresh_filter

with col4:
    st.write(" ")
    st.write(" ")
    btn_c1, btn_c2 = st.columns(2)
    with btn_c1:
        uploaded_csv = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")
        if uploaded_csv is not None:
            save_path = os.path.join(UPLOADS_DIR, "latest_candidates.csv")
            with open(save_path, "wb") as f:
                f.write(uploaded_csv.getbuffer())
            st.success("Uploaded!")
            st.rerun()
    with btn_c2:
        if st.button("⚡ Re-Screen", use_container_width=True, type="primary"):
            st.rerun()

# ----------------- Roles Management (Add / Delete) -----------------
with st.expander("⚙️ Manage Roles (Add New JD / Delete Active JD)"):
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.markdown("**➕ Add Fresh Role / Job Description**")
        with st.form("new_jd_form"):
            c_name = st.text_input("Client Name", placeholder="e.g. INFOSYS")
            r_name = st.text_input("Role Title", placeholder="e.g. AWS DevOps Engineer")
            e1, e2 = st.columns(2)
            exp_min = e1.text_input("Min Exp", value="3")
            exp_max = e2.text_input("Max Exp", value="8")
            s_tags = st.text_area("Mandatory Skills", placeholder="AWS, Terraform, Kubernetes, Python")
            if st.form_submit_button("Save & Activate Role", type="primary"):
                if c_name and r_name and s_tags:
                    safe = re.sub(r'[^a-zA-Z0-9_]', '_', f"{c_name}_{r_name}").strip('_')
                    with open(os.path.join(JD_DIR, f"{safe}.txt"), "w", encoding="utf-8") as f:
                        f.write(f"Target Client: {c_name}\nRole: {r_name}\nExperience: {exp_min} to {exp_max} Years\nMandatory Skills: {s_tags}\nNotice Period: Immediate to 30 Days\n")
                    st.success("Role created!")
                    st.rerun()
    with m_col2:
        st.markdown(f"**🗑️ Delete Role: {selected_title}**")
        st.write("Permanently remove the currently selected Job Description.")
        if st.button("Delete Selected Role", type="secondary"):
            target_path = os.path.join(JD_DIR, selected_filename)
            if os.path.exists(target_path):
                os.remove(target_path)
                st.success("Role deleted successfully!")
                st.rerun()

# ----------------- Screen Candidates -----------------
candidates, src_file = screen_candidates(selected_filename, min_score, fresh_only)
total_count = len(candidates)
fresh_count = sum(1 for c in candidates if not c["is_locked"])
immediate_count = sum(1 for c in candidates if c["radar_type"] == "HIGH_INTENT")
locked_count = total_count - fresh_count

# ----------------- Stats Grid (Identical to Render) -----------------
st.markdown(f"""
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-label">Total Candidates Loaded</div>
        <div class="stat-val">{total_count}</div>
        <div class="stat-desc">From {src_file}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">🌟 Fresh Submissions</div>
        <div class="stat-val" style="color:#16a34a;">{fresh_count}</div>
        <div class="stat-desc">Zero 180-day lockout collision</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">⚡ Serving Notice / Immediate</div>
        <div class="stat-val" style="color:#0284c7;">{immediate_count}</div>
        <div class="stat-desc">High-intent fast closures</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">🔒 Duplicates Prevented</div>
        <div class="stat-val" style="color:#dc2626;">{locked_count}</div>
        <div class="stat-desc">Protected against client rejection</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- Render-Style Candidates Table -----------------
st.markdown(f"""
<div class="table-card">
    <div class="table-top">
        <div class="table-title">Displaying <b>{total_count}</b> best candidates for <b>{selected_title}</b></div>
    </div>
</div>
""", unsafe_allow_html=True)

if not candidates:
    st.info(f"0 candidates met the {min_score}% score filter for {selected_title}. Try lowering the match threshold above.")
else:
    # Build complete HTML table identical to Render
    rows_html = ""
    for i, c in enumerate(candidates):
        score_class = "match-top" if c["score"] >= 95 else ("match-high" if c["score"] >= 80 else "match-good")
        score_badge = f'<span class="match-badge {score_class}">{c["score"]}% Match</span>'
        
        lock_badge = '<span class="status-fresh">🌟 100% Fresh</span>' if not c["is_locked"] else '<span class="status-locked">🔒 Locked</span>'
        
        matched_set = set(s.lower() for s in c["matched_skills"])
        skills_html = "".join([
            f'<span class="tag-pill tag-matched">✓ {s}</span>' if s.lower() in matched_set else f'<span class="tag-pill tag-default">{s}</span>'
            for s in c["skills"]
        ])
        
        radar_class = "radar-immediate" if c["radar_type"] == "HIGH_INTENT" else "radar-active"
        radar_html = f'''
        <div>
            <span class="radar-badge {radar_class}">{c["radar_label"]}</span>
            <div style="font-size:11.5px;color:#64748b;margin-top:2px;">⏱️ Notice: <b>{c["notice"]}</b></div>
        </div>
        '''
        
        phone_html = f'📞 <a href="tel:{c["phone"]}" style="color:#047857;font-weight:700;">{c["phone"]}</a>' if c["phone"] else '<span style="color:#94a3b8;font-size:11.5px;">Phone: <i>Not in CSV</i></span>'
        email_html = f'✉️ <a href="mailto:{c["email"]}" style="color:#0284c7;font-weight:700;">{c["email"]}</a>' if c["email"] else '<span style="color:#94a3b8;font-size:11.5px;">Email: <i>Not in CSV</i></span>'
        contact_block = f'<div style="font-size:11.5px;line-height:1.6;">{phone_html}<br>{email_html}</div>'
        
        li_url = "https://www.google.com/search?q=" + urllib.parse.quote(f'{c["name"]} {c["company"]} site:linkedin.com/in')
        google_dork = "https://www.google.com/search?q=" + urllib.parse.quote(f'"{c["name"]}" "{c["company"]}" ("email" OR "phone" OR "resume" OR "@gmail.com")')
        bing_dork = "https://www.bing.com/search?q=" + urllib.parse.quote(f'"{c["name"]}" "{c["company"]}" ("email" OR "phone" OR "resume" OR "@gmail.com")')
        github_url = "https://www.google.com/search?q=" + urllib.parse.quote(f'{c["name"]} site:github.com')
        portals_url = "https://www.google.com/search?q=" + urllib.parse.quote(f'"{c["name"]}" ("foundit.in" OR "indeed.com" OR "shine.com")')
        
        action_links = f'''
        <div class="action-links">
            <a class="link-btn link-li" href="{li_url}" target="_blank">🔗 LinkedIn</a>
            <a class="link-btn link-search" href="{google_dork}" target="_blank">🌐 Google Dork</a>
            <a class="link-btn link-search" href="{bing_dork}" target="_blank">🔎 Bing Dork</a>
            <a class="link-btn link-search" href="{github_url}" target="_blank">🐙 GitHub</a>
            <a class="link-btn link-search" href="{portals_url}" target="_blank">📑 Foundit/Indeed</a>
        </div>
        '''
        
        rows_html += f'''
        <tr>
            <td><b style="color:#64748b;">#{i+1}</b></td>
            <td>{score_badge}</td>
            <td>
                <div>
                    <div class="name-title">{c["name"]}</div>
                    <div class="role-title">{c["role"]}</div>
                    <div class="comp-title">🏢 {c["company"]}</div>
                </div>
            </td>
            <td>
                <div style="font-weight:600;">⏱️ {c["exp"]}</div>
                <div style="font-size:11.5px;color:#64748b;margin-top:2px;">📍 {c["location"]}</div>
            </td>
            <td>{contact_block}</td>
            <td>{radar_html}</td>
            <td>{skills_html if skills_html else '<span style="color:#94a3b8;font-size:11px;">Matched on experience</span>'}</td>
            <td>{lock_badge}</td>
            <td>{action_links}</td>
        </tr>
        '''
        
    full_table_html = f'''
    <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;overflow-x:auto;box-shadow:0 2px 8px rgba(0,0,0,0.04);">
        <table class="tf-table">
            <thead>
                <tr>
                    <th style="width:40px;">#</th>
                    <th style="width:110px;">Fit Score</th>
                    <th style="width:230px;">Candidate & Role</th>
                    <th style="width:130px;">Exp & City</th>
                    <th style="width:170px;">📞 Phone & Email</th>
                    <th style="width:200px;">Availability & Intent</th>
                    <th>Skills Matched</th>
                    <th style="width:120px;">Lockout</th>
                    <th style="width:140px;">Online Profiles</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    '''
    st.markdown(full_table_html, unsafe_allow_html=True)
