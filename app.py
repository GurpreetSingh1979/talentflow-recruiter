"""
TalentFlow Cloud - Multi-User Recruiter Screening & Duplicate Lockout Hub
Built by Gurpreet Singh for 20-Recruiter Operations
"""

import os
import re
import csv
import io
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JD_DIR = os.path.join(BASE_DIR, "ACTIVE_JDS")
DB_PATH = os.path.join(BASE_DIR, "candidate_vault.db")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(JD_DIR, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

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
        print("DB Init warning:", e)

init_db()

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
        clean_title = f.replace(".txt", "").replace("_", " ")
        result.append({"filename": f, "title": clean_title})
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
            return True, f"Locked ({row[0]})"
        return False, None
    except Exception:
        return False, None

def evaluate_readiness(notice, role, skills_text):
    notice_clean = notice.lower().strip()
    is_immediate = any(k in notice_clean for k in ["immediate", "15 days", "serving", "1 month", "30 days"])
    has_certs = any(k in skills_text.lower() for k in ["certified", "certification", "trailhead", "ranger", "superbadge", "cert"])
    
    if is_immediate and has_certs:
        return "HIGH_INTENT", "⚡ Actively Interviewing (Notice + Certs)"
    elif is_immediate:
        return "HIGH_INTENT", "🟢 High Availability (Serving Notice / Immediate)"
    elif has_certs:
        return "INTERVIEW_READY", "🎓 Active Learner (Recent Certifications)"
    else:
        return "WARM_ACTIVE", "🟡 Profile Updated Recently"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gurpreet's TalentFlow - Cloud Recruiter Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #f8fafc;
            --surface: #ffffff;
            --border: #e2e8f0;
            --primary: #2563eb;
            --primary-light: #eff6ff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --green: #16a34a;
            --green-light: #f0fdf4;
            --amber: #d97706;
            --amber-light: #fffbeb;
            --red: #dc2626;
            --red-light: #fef2f2;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text-main); padding: 24px 32px; }
        .container { max-width: 1650px; margin: 0 auto; }

        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
        .logo-group h1 { font-size: 24px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; display: flex; align-items: center; gap: 10px; }
        .logo-group h1 span { color: var(--primary); }
        .logo-group p { font-size: 14px; color: var(--text-muted); margin-top: 4px; font-weight: 500; }
        .header-badges { display: flex; gap: 12px; }
        .badge-pill { font-size: 13px; font-weight: 700; padding: 8px 16px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 6px; }
        .badge-zero { background: var(--green-light); color: var(--green); border: 1px solid #bbf7d0; }
        .badge-owner { background: var(--primary-light); color: var(--primary); border: 1px solid #bfdbfe; }

        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .stat-label { font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
        .stat-val { font-size: 26px; font-weight: 800; color: var(--text-main); margin-top: 6px; }
        .stat-desc { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

        .filter-bar { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 20px 24px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
        .filter-controls { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; }
        .filter-item { display: flex; flex-direction: column; gap: 6px; }
        .filter-item label { font-size: 12px; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.4px; }
        .filter-item select, .filter-item input { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px 14px; font-size: 13px; font-weight: 600; color: #1e293b; outline: none; transition: all 0.2s; min-width: 200px; }
        .filter-item select:focus, .filter-item input:focus { border-color: var(--primary); background: #fff; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }

        .btn-group { display: flex; gap: 12px; align-items: flex-end; }
        .btn { padding: 11px 22px; font-size: 13px; font-weight: 700; border-radius: 8px; cursor: pointer; border: none; display: inline-flex; align-items: center; gap: 8px; transition: all 0.2s; text-decoration: none; }
        .btn-primary { background: var(--primary); color: #fff; box-shadow: 0 2px 8px rgba(37,99,235,0.3); }
        .btn-primary:hover { background: #1d4ed8; transform: translateY(-1px); }
        .btn-success { background: var(--green); color: #fff; box-shadow: 0 2px 8px rgba(22,163,74,0.3); }
        .btn-success:hover { background: #15803d; }
        .btn-upload { background: #475569; color: #fff; }
        .btn-upload:hover { background: #334155; }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

        .banner { padding: 14px 20px; border-radius: 10px; font-size: 13px; font-weight: 600; margin-bottom: 20px; display: none; }
        .banner-info { background: var(--primary-light); color: var(--primary); border: 1px solid #bfdbfe; }
        .banner-success { background: var(--green-light); color: var(--green); border: 1px solid #bbf7d0; }
        .banner-error { background: var(--red-light); color: var(--red); border: 1px solid #fecaca; }

        .table-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); overflow: hidden; }
        .table-top { padding: 16px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: #fafafa; }
        .table-title { font-size: 15px; font-weight: 700; color: #1e293b; }
        .search-box { padding: 8px 14px; font-size: 13px; border: 1px solid #cbd5e1; border-radius: 6px; width: 260px; outline: none; }

        .table-responsive { overflow-x: auto; max-height: 700px; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
        th { background: #f1f5f9; color: #475569; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; padding: 14px 18px; border-bottom: 2px solid var(--border); position: sticky; top: 0; z-index: 2; }
        td { padding: 16px 18px; border-bottom: 1px solid var(--border); vertical-align: middle; }
        tr:hover td { background: #f8fafc; }

        .match-badge { display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 800; padding: 6px 12px; border-radius: 8px; }
        .match-top { background: var(--green-light); color: var(--green); border: 1px solid #bbf7d0; }
        .match-high { background: var(--primary-light); color: var(--primary); border: 1px solid #bfdbfe; }
        .match-good { background: var(--amber-light); color: var(--amber); border: 1px solid #fde68a; }

        .cand-info .name { font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 4px; }
        .cand-info .role { font-size: 13px; font-weight: 600; color: var(--primary); }
        .cand-info .company { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

        .tag-pill { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; margin: 2px; }
        .tag-matched { background: var(--primary-light); color: var(--primary); border: 1px solid #bfdbfe; }
        .tag-default { background: #f1f5f9; color: #64748b; }

        .status-fresh { background: var(--green-light); color: var(--green); border: 1px solid #bbf7d0; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; display: inline-flex; align-items: center; gap: 4px; }
        .status-locked { background: var(--red-light); color: var(--red); border: 1px solid #fecaca; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; display: inline-flex; align-items: center; gap: 4px; }

        .radar-badge { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; display: inline-block; margin-bottom: 4px; }
        .radar-immediate { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
        .radar-active { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }

        .action-links { display: flex; flex-direction: column; gap: 5px; min-width: 160px; }
        .link-btn { text-decoration: none; font-size: 11px; font-weight: 700; padding: 6px 12px; border-radius: 6px; text-align: center; display: inline-flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.15s; }
        .link-li { background: #0a66c2; color: #fff; }
        .link-li:hover { background: #084e96; }
        .link-search { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
        .link-search:hover { background: #e2e8f0; }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <div class="logo-group">
            <h1>⚡ Talent<span>Flow</span> Cloud Screening Portal</h1>
            <p>Automated Candidate Sourcing, Duplicate Lockout Guard & Intent Radar for Recruitment Teams</p>
        </div>
        <div class="header-badges">
            <button onclick="openInstallModal()" class="badge-pill" style="background:#4338ca;color:#fff;border:none;cursor:pointer;">
                🚀 Install 100+ Naukri Extractor
            </button>
            <span class="badge-pill badge-zero">🛡️ 0 Recruiter Credits Used</span>
            <span class="badge-pill badge-owner">👤 Designed by Gurpreet Singh</span>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Candidates Loaded</div>
            <div class="stat-val" id="countTotal">0</div>
            <div class="stat-desc">From latest batch upload</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">🌟 Fresh Submissions</div>
            <div class="stat-val" style="color:var(--green);" id="countFresh">0</div>
            <div class="stat-desc">Zero 180-day lockout collision</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">⚡ Serving Notice / Immediate</div>
            <div class="stat-val" style="color:#0284c7;" id="countImmediate">0</div>
            <div class="stat-desc">High-intent fast closures</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">🔒 Duplicates Prevented</div>
            <div class="stat-val" style="color:var(--red);" id="countLocked">0</div>
            <div class="stat-desc">Protected against client rejection</div>
        </div>
    </div>

    <div class="filter-bar">
        <div class="filter-controls">
            <div class="filter-item">
                <label>1. Select Job Role (JD)</label>
                <div style="display:flex;gap:8px;">
                    <select id="jdSelect" onchange="autoLoad()">
                        {% for jd in jds %}
                        <option value="{{ jd.filename }}">{{ jd.title }}</option>
                        {% endfor %}
                    </select>
                    <button onclick="openCreateJDModal()" class="btn" style="background:#0284c7;color:#fff;padding:8px 12px;font-size:12px;" title="Add New Role / JD">
                        ➕ New Role
                    </button>
                </div>
            </div>

            <div class="filter-item">
                <label>2. Match Threshold</label>
                <select id="minScoreSelect" onchange="autoLoad()">
                    <option value="80" selected>80% to 100% (Strict Best Matches)</option>
                    <option value="90">90% to 100% (Top Tier Only)</option>
                    <option value="70">70% to 100% (Broader Pool)</option>
                    <option value="0">All Scores (0% - 100%)</option>
                </select>
            </div>

            <div class="filter-item">
                <label>3. Duplicate Protection</label>
                <select id="freshSelect" onchange="autoLoad()">
                    <option value="true" selected>🌟 Fresh Only (Hide Prior Submissions)</option>
                    <option value="false">Show All (Include Locked)</option>
                </select>
            </div>
        </div>

        <div class="btn-group">
            <input type="file" id="csvFileInput" accept=".csv" style="display:none;" onchange="handleFileUpload(event)">
            <button class="btn btn-upload" onclick="document.getElementById('csvFileInput').click()">
                <span>📤 Upload Candidate CSV</span>
            </button>
            <button class="btn btn-primary" id="btnAttach" onclick="autoLoad()">
                <span>⚡ Re-Screen</span>
            </button>
            <button class="btn btn-success" id="btnExport" style="display:none;" onclick="exportCSV()">
                <span>📥 Export Shortlist</span>
            </button>
        </div>
    </div>

    <div id="statusBanner" class="banner"></div>

    <div class="table-card">
        <div class="table-top">
            <div class="table-title" id="statsText">Upload a CSV or click Re-Screen to view candidate pool</div>
            <input type="text" id="quickSearch" class="search-box" placeholder="🔍 Search candidate, company, city..." onkeyup="filterLive()">
        </div>

        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th style="width:50px;">#</th>
                        <th style="width:100px;">Fit Score</th>
                        <th style="width:240px;">Candidate & Role</th>
                        <th style="width:140px;">Exp & City</th>
                        <th style="width:170px;">📞 Phone & Email</th>
                        <th style="width:200px;">Availability & Intent</th>
                        <th>Skills Matched</th>
                        <th style="width:130px;">Lockout</th>
                        <th style="width:150px;">Online Profiles</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                    <tr>
                        <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 50px;">
                            Click <b>📤 Upload Candidate CSV</b> to upload a batch or <b>⚡ Re-Screen</b> to load existing candidates.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>

<div id="installModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center;">
    <div style="background:#fff;border-radius:14px;max-width:650px;width:90%;padding:28px;box-shadow:0 20px 40px rgba(0,0,0,0.3);position:relative;">
        <h2 style="font-size:20px;font-weight:800;color:#0f172a;margin-bottom:8px;">🚀 1-Click Naukri Extractor Setup</h2>
        <p style="font-size:13px;color:#64748b;margin-bottom:20px;">Share this button with all 20 recruiters. They just drag it to their bookmarks bar once!</p>

        <div style="background:#f1f5f9;border:2px dashed #cbd5e1;border-radius:10px;padding:20px;text-align:center;margin-bottom:20px;">
            <p style="font-size:13px;font-weight:600;color:#334155;margin-bottom:12px;">👉 Drag this purple button directly to your Chrome Bookmarks Bar:</p>
            <a id="dragBookmarklet" href="#" style="background:#4f46e5;color:#fff;padding:12px 24px;border-radius:8px;font-weight:800;font-size:14px;text-decoration:none;display:inline-flex;align-items:center;gap:8px;box-shadow:0 4px 12px rgba(79,70,229,0.4);cursor:grab;">
                ⚡ Auto-Crawl 100+ Naukri
            </a>
        </div>

        <div style="font-size:13px;color:#334155;line-height:1.6;margin-bottom:20px;">
            <b>How any recruiter uses it:</b><br>
            1. Open any candidate search on Naukri Resdex.<br>
            2. Click the <b>⚡ Auto-Crawl 100+ Naukri</b> button on your Chrome bookmarks bar.<br>
            3. Enter how many pages to crawl (e.g. <code>3</code> for 120 candidates, <code>5</code> for 200).<br>
            4. Upload the downloaded CSV to this portal to screen for 80-100% matches & client lockouts.
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;">
            <button onclick="copyCodeFallback()" class="btn" style="background:#0f172a;color:#fff;padding:8px 16px;font-size:12px;">📋 Copy Code Manually</button>
            <button onclick="closeInstallModal()" class="btn btn-primary" style="padding:8px 20px;">Done</button>
        </div>
    </div>
</div>

<div id="createJDModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center;">
    <div style="background:#fff;border-radius:14px;max-width:550px;width:90%;padding:28px;box-shadow:0 20px 40px rgba(0,0,0,0.3);">
        <h2 style="font-size:18px;font-weight:800;color:#0f172a;margin-bottom:6px;">➕ Add Fresh Role / Job Description</h2>
        <p style="font-size:13px;color:#64748b;margin-bottom:18px;">Create a new role so the bot can automatically score incoming candidates against it.</p>

        <div style="display:flex;flex-direction:column;gap:12px;">
            <div>
                <label style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">Client / Account Name</label>
                <input type="text" id="newClient" placeholder="e.g. LTIMINDTREE, CAPGEMINI, TCS" style="width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;margin-top:4px;">
            </div>
            <div>
                <label style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">Job Title / Role</label>
                <input type="text" id="newRole" placeholder="e.g. AWS DevOps Engineer, React Developer" style="width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;margin-top:4px;">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                <div>
                    <label style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">Min Experience (Yrs)</label>
                    <input type="number" id="newMinExp" value="3" style="width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;margin-top:4px;">
                </div>
                <div>
                    <label style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">Max Experience (Yrs)</label>
                    <input type="number" id="newMaxExp" value="8" style="width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;margin-top:4px;">
                </div>
            </div>
            <div>
                <label style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">Mandatory Skills (Comma-Separated)</label>
                <input type="text" id="newSkills" placeholder="e.g. Docker, Kubernetes, Terraform, CI/CD, Python" style="width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;margin-top:4px;">
            </div>
        </div>

        <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:22px;">
            <button onclick="closeCreateJDModal()" class="btn" style="background:#f1f5f9;color:#475569;padding:9px 16px;">Cancel</button>
            <button onclick="saveNewJD()" class="btn btn-primary" style="padding:9px 20px;">Save & Activate Role</button>
        </div>
    </div>
</div>

<script>
var bookmarkletCode = "";
fetch('/api/get-bookmarklet')
    .then(r => r.json())
    .then(d => {
        bookmarkletCode = d.code;
        document.getElementById('dragBookmarklet').href = bookmarkletCode;
    });

function openCreateJDModal() {
    document.getElementById('createJDModal').style.display = 'flex';
}
function closeCreateJDModal() {
    document.getElementById('createJDModal').style.display = 'none';
}
function saveNewJD() {
    var client = document.getElementById('newClient').value.trim();
    var role = document.getElementById('newRole').value.trim();
    var minExp = document.getElementById('newMinExp').value.trim();
    var maxExp = document.getElementById('newMaxExp').value.trim();
    var skills = document.getElementById('newSkills').value.trim();

    if (!client || !role || !skills) {
        alert("Please fill in Client Name, Role, and Mandatory Skills.");
        return;
    }

    fetch('/api/create-jd', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client: client, role: role, min_exp: minExp, max_exp: maxExp, skills: skills })
    })
    .then(r => r.json())
    .then(d => {
        if (!d.success) {
            alert("Error: " + d.error);
            return;
        }
        alert("✅ Role '" + role + "' created successfully!");
        closeCreateJDModal();
        window.location.reload();
    })
    .catch(err => alert("Failed to save: " + err.message));
}


function openInstallModal() {
    document.getElementById('installModal').style.display = 'flex';
}
function closeInstallModal() {
    document.getElementById('installModal').style.display = 'none';
}
function copyCodeFallback() {
    navigator.clipboard.writeText(bookmarkletCode).then(() => {
        alert("✅ Extractor code copied to your clipboard!");
    });
}

var currentJD = '';

function showBanner(text, type) {
    var b = document.getElementById('statusBanner');
    b.className = 'banner banner-' + type;
    b.innerHTML = text;
    b.style.display = 'block';
}

function handleFileUpload(e) {
    var file = e.target.files[0];
    if (!file) return;

    var formData = new FormData();
    formData.append('file', file);

    showBanner('📤 Uploading and screening ' + file.name + '...', 'info');

    fetch('/api/upload-csv', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            showBanner('Upload error: ' + data.error, 'error');
            return;
        }
        showBanner('✅ Uploaded ' + data.filename + ' successfully! Auto-screening now...', 'success');
        autoLoad();
    })
    .catch(err => {
        showBanner('Upload failed: ' + err.message, 'error');
    });
}

function autoLoad() {
    var jdFile = document.getElementById('jdSelect').value;
    var minScore = document.getElementById('minScoreSelect').value;
    var freshOnly = document.getElementById('freshSelect').value;
    var btn = document.getElementById('btnAttach');

    btn.disabled = true;
    btn.innerHTML = '⏳ Screening...';

    var url = '/api/screen-candidates?jd=' + encodeURIComponent(jdFile) +
              '&min_score=' + encodeURIComponent(minScore) +
              '&fresh_only=' + encodeURIComponent(freshOnly);

    fetch(url)
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '⚡ Re-Screen';

            if (!data.success) {
                // Try loading from localStorage if server has no uploaded file
                var cached = localStorage.getItem('tf_last_candidates');
                if (cached) {
                    try {
                        var parsed = JSON.parse(cached);
                        currentCandidates = parsed;
                        renderTable(parsed);
                        document.getElementById('countTotal').innerText = parsed.length;
                        showBanner('ℹ️ Restored ' + parsed.length + ' candidates from your previous session.', 'info');
                        return;
                    } catch(e) {}
                }
                showBanner('ℹ️ ' + data.error, 'info');
                return;
            }

            currentCandidates = data.candidates || [];
            currentJD = data.jd_title || '';
            localStorage.setItem('tf_last_candidates', JSON.stringify(currentCandidates));

            var total = currentCandidates.length;
            var locked = currentCandidates.filter(c => c.is_locked).length;
            var fresh = total - locked;
            var immediate = currentCandidates.filter(c => c.radar_type === 'HIGH_INTENT').length;

            document.getElementById('countTotal').innerText = total;
            document.getElementById('countFresh').innerText = fresh;
            document.getElementById('countImmediate').innerText = immediate;
            document.getElementById('countLocked').innerText = locked;

            showBanner('✅ Loaded <b>' + total + ' Candidates</b> from ' + data.filename + ' (0 portal credits used)', 'success');
            document.getElementById('statsText').innerHTML = 'Displaying <b>' + total + '</b> best candidates for <b>' + currentJD + '</b>';

            if (total > 0) {
                document.getElementById('btnExport').style.display = 'inline-flex';
            }

            renderTable(currentCandidates);
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '⚡ Re-Screen';
            var cached = localStorage.getItem('tf_last_candidates');
            if (cached) {
                var parsed = JSON.parse(cached);
                currentCandidates = parsed;
                renderTable(parsed);
                document.getElementById('countTotal').innerText = parsed.length;
                showBanner('Loaded ' + parsed.length + ' saved candidates.', 'info');
            } else {
                showBanner('Screening failed: ' + err.message, 'error');
            }
        });
}

function filterLive() {
    var q = document.getElementById('quickSearch').value.toLowerCase();
    if (!q) {
        renderTable(currentCandidates);
        return;
    }
    var filtered = currentCandidates.filter(function(c) {
        return (c.name || '').toLowerCase().includes(q) ||
               (c.role || '').toLowerCase().includes(q) ||
               (c.company || '').toLowerCase().includes(q) ||
               (c.location || '').toLowerCase().includes(q);
    });
    renderTable(filtered);
}

function renderTable(candidates) {
    var tbody = document.getElementById('tableBody');
    if (!candidates || candidates.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:50px;color:var(--text-muted);">No candidates match your current filter settings. Try adjusting the match score or unchecking Fresh Only.</td></tr>';
        return;
    }

    var html = '';
    candidates.forEach(function(c, i) {
        var scoreClass = c.match_score >= 95 ? 'match-top' : (c.match_score >= 85 ? 'match-high' : 'match-good');
        var scoreBadge = '<span class="match-badge ' + scoreClass + '">' + c.match_score + '% Match</span>';

        var lockBadge = c.is_locked ? 
            ('<span class="status-locked">🔒 ' + c.lock_reason + '</span>') : 
            ('<span class="status-fresh">🌟 100% Fresh</span>');

        var matchedSet = new Set((c.matched_skills || []).map(function(s){ return s.toLowerCase(); }));
        var skillsHtml = (c.skills || []).map(function(s) {
            var isMatched = matchedSet.has(s.toLowerCase());
            return '<span class="tag-pill ' + (isMatched ? 'tag-matched' : 'tag-default') + '">' + (isMatched ? '✓ ' : '') + s + '</span>';
        }).join('');

        var radarPillClass = c.radar_type === 'HIGH_INTENT' ? 'radar-immediate' : 'radar-active';
        var radarHtml = '<div>' +
            '<span class="radar-badge ' + radarPillClass + '">' + c.radar_label + '</span>' +
            '<div style="font-size:12px;color:var(--text-muted);margin-top:2px;">⏱️ Notice: <b>' + (c.notice || 'Serving Notice / Immediate') + '</b></div>' +
        '</div>';

        var liUrl = c.linkedin || ('https://www.google.com/search?q=' + encodeURIComponent(c.name + ' ' + (c.company || '') + ' site:linkedin.com/in'));
        var githubUrl = 'https://www.google.com/search?q=' + encodeURIComponent(c.name + ' site:github.com');
        var founditUrl = 'https://www.google.com/search?q=' + encodeURIComponent(c.name + ' ' + (c.company || '') + ' site:foundit.in');
        var contactQuery = encodeURIComponent(c.name + ' "' + (c.company || '') + '" ("email" OR "phone" OR "resume" OR "@gmail.com")');

        var phoneHtml = c.phone ? ('📞 <a href="tel:' + c.phone + '" style="color:#047857;font-weight:700;">' + c.phone + '</a>') : '<span style="color:#94a3b8;font-size:12px;">Phone: <i>Not public</i></span>';
        var emailHtml = c.email ? ('✉️ <a href="mailto:' + c.email + '" style="color:#0284c7;font-weight:700;">' + c.email + '</a>') : '<span style="color:#94a3b8;font-size:12px;">Email: <i>Not public</i></span>';
        var contactBlock = '<div style="font-size:12px;line-height:1.6;">' + phoneHtml + '<br>' + emailHtml + '</div>';

        html += '<tr>' +
            '<td><b style="color:#64748b;">#' + (i + 1) + '</b></td>' +
            '<td>' + scoreBadge + '</td>' +
            '<td>' +
                '<div class="cand-info">' +
                    '<div class="name">' + c.name + '</div>' +
                    '<div class="role">' + (c.role || 'Developer') + '</div>' +
                    '<div class="company">🏢 ' + (c.company || 'Confidential') + '</div>' +
                '</div>' +
            '</td>' +
            '<td>' +
                '<div style="font-weight:600;">⏱️ ' + (c.exp || 'N/A') + '</div>' +
                '<div style="font-size:12px;color:var(--text-muted);margin-top:3px;">📍 ' + (c.location || 'Pan India') + '</div>' +
            '</td>' +
            '<td>' + contactBlock + '</td>' +
            '<td>' + radarHtml + '</td>' +
            '<td>' + (skillsHtml || '<span style="color:var(--text-muted);font-size:12px;">Matched on experience</span>') + '</td>' +
            '<td>' + lockBadge + '</td>' +
            '<td>' +
                '<div class="action-links">' +
                    '<a class="link-btn link-li" href="' + liUrl + '" target="_blank">🔗 LinkedIn</a>' +
                    '<a class="link-btn link-search" href="' + githubUrl + '" target="_blank">🐙 GitHub</a>' +
                    '<a class="link-btn link-search" href="' + founditUrl + '" target="_blank">🔍 Foundit</a>' +
                '</div>' +
            '</td>' +
        '</tr>';
    });
    tbody.innerHTML = html;
}

function fetchLiveContact(name, company, index) {
    var btn = document.getElementById('btn-fetch-' + index);
    var box = document.getElementById('contact-info-' + index);
    btn.disabled = true;
    btn.innerHTML = '⏳ Searching Web...';

    fetch('/api/find-candidate-contact?name=' + encodeURIComponent(name) + '&company=' + encodeURIComponent(company))
        .then(r => r.json())
        .then(d => {
            btn.style.display = 'none';
            box.style.display = 'block';
            var html = '';
            if (d.phone && d.phone !== 'Not found publicly') {
                html += '📞 <b>Phone:</b> <a href="tel:' + d.phone + '" style="color:#047857;font-weight:700;">' + d.phone + '</a><br>';
            } else {
                html += '📞 <b>Phone:</b> <span style="color:#64748b;">Not public</span><br>';
            }

            if (d.email && d.email !== 'Not found publicly') {
                html += '✉️ <b>Email:</b> <a href="mailto:' + d.email + '" style="color:#047857;font-weight:700;">' + d.email + '</a>';
            } else {
                html += '✉️ <b>Email:</b> <span style="color:#64748b;">Not public</span>';
            }

            if (d.linkedin) {
                html += '<br>🔗 <a href="' + d.linkedin + '" target="_blank" style="color:#0a66c2;font-weight:700;">Verified LinkedIn</a>';
            }
            box.innerHTML = html;
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '⚡ Get Phone/Email';
            alert("Search failed: " + err.message);
        });
}

function exportCSV() {
    if (!currentCandidates || currentCandidates.length === 0) return;
    var csv = 'Rank,Match_Score,Name,Role,Company,Experience,Location,Notice_Period,Readiness_Status,Matched_Skills,All_Skills,Lockout_Status,LinkedIn_URL,GitHub_Search,Other_Portals_Search,Contact_Dork\\n';
    currentCandidates.forEach(function(c, i) {
        var liUrl = c.linkedin || ('https://www.google.com/search?q=' + encodeURIComponent(c.name + ' ' + (c.company || '') + ' site:linkedin.com/in'));
        var ghUrl = 'https://www.google.com/search?q=' + encodeURIComponent(c.name + ' site:github.com');
        var founditUrl = 'https://www.google.com/search?q=' + encodeURIComponent(c.name + ' ' + (c.company || '') + ' site:foundit.in');
        var dorkUrl = 'https://www.google.com/search?q=' + encodeURIComponent(c.name + ' "' + (c.company || '') + '" ("email" OR "phone" OR "resume" OR "@gmail.com")');

        var row = [
            i + 1,
            c.match_score + '%',
            '"' + (c.name || '').replace(/"/g, '""') + '"',
            '"' + (c.role || '').replace(/"/g, '""') + '"',
            '"' + (c.company || '').replace(/"/g, '""') + '"',
            '"' + (c.exp || '').replace(/"/g, '""') + '"',
            '"' + (c.location || '').replace(/"/g, '""') + '"',
            '"' + (c.notice || '').replace(/"/g, '""') + '"',
            '"' + (c.radar_label || '').replace(/"/g, '""') + '"',
            '"' + ((c.matched_skills || []).join(', ')).replace(/"/g, '""') + '"',
            '"' + ((c.skills || []).join(', ')).replace(/"/g, '""') + '"',
            c.is_locked ? 'LOCKED' : 'FRESH_SAFE',
            '"' + liUrl + '"',
            '"' + ghUrl + '"',
            '"' + founditUrl + '"',
            '"' + dorkUrl + '"'
        ];
        csv += row.join(',') + '\\n';
    });
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'Shortlist_' + (currentJD.replace(/\\s+/g, '_') || 'Candidates') + '_' + new Date().toISOString().slice(0,10) + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

window.addEventListener('DOMContentLoaded', function() {
    autoLoad();
});
</script>

</body>
</html>
"""

@app.route("/")
def index():
    jds = get_available_jds()
    return render_template_string(HTML_TEMPLATE, jds=jds)

@app.route("/api/get-bookmarklet", methods=["GET"])
def api_get_bookmarklet():
    b_path = os.path.join(BASE_DIR, "bookmarklet.txt")
    code = ""
    if os.path.exists(b_path):
        with open(b_path, "r", encoding="utf-8") as f:
            code = f.read().strip()
    return jsonify({"code": code})

@app.route("/api/create-jd", methods=["POST"])
def api_create_jd():
    data = request.get_json() or {}
    client = data.get("client", "").strip().upper()
    role = data.get("role", "").strip()
    min_exp = data.get("min_exp", "3").strip()
    max_exp = data.get("max_exp", "8").strip()
    skills = data.get("skills", "").strip()

    if not client or not role or not skills:
        return jsonify({"success": False, "error": "Missing required fields"})

    safe_title = re.sub(r'[^a-zA-Z0-9_]', '_', f"{client}_{role}").strip('_')
    filename = f"{safe_title}.txt"
    filepath = os.path.join(JD_DIR, filename)

    content = f"""Target Client: {client}
Role: {role}
Experience: {min_exp} to {max_exp} Years
Mandatory Skills: {skills}
Notice Period: Immediate to 30 Days
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return jsonify({"success": True, "filename": filename})

@app.route("/api/upload-csv", methods=["POST"])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part in request"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected"})
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "error": "Only CSV files allowed"})

    save_path = os.path.join(UPLOADS_DIR, "latest_candidates.csv")
    file.save(save_path)
    return jsonify({"success": True, "filename": file.filename})

@app.route("/api/screen-candidates", methods=["GET"])
def api_screen_candidates():
    jd_filename = request.args.get("jd", "1_LTIMindtree_Salesforce_CPQ.txt")
    min_score = int(request.args.get("min_score", 80))
    fresh_only = request.args.get("fresh_only", "true").lower() == "true"

    jd = parse_jd(jd_filename)
    jd_title = jd_filename.replace(".txt", "").replace("_", " ")

    latest_file = os.path.join(UPLOADS_DIR, "latest_candidates.csv")
    if not os.path.exists(latest_file):
        return jsonify({"success": False, "error": "No candidate CSV has been uploaded yet. Please click 'Upload Candidate CSV' to get started."})

    candidates = []
    try:
        with open(latest_file, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "").strip()
                if not name:
                    continue

                role = row.get("Current_Role", row.get("Role", "")).strip()
                exp = row.get("Experience", "").strip()
                loc = row.get("Location", "").strip()
                skills_raw = row.get("Key_Skills", row.get("Skills", "")).strip()
                notice = row.get("Notice_Period", "").strip()

                exp_years = 0.0
                m = re.search(r"(\d+)y\s*(\d*)m?", exp, re.I)
                if m:
                    exp_years = round(int(m.group(1)) + (int(m.group(2) or 0) / 12.0), 1)

                if exp_years > 0 and (exp_years < jd["min_exp"] - 0.5 or exp_years > jd["max_exp"] + 1.5):
                    continue

                full_text = f"{name} {role} {skills_raw}".lower()
                matched = [s for s in jd["skills"] if re.search(r"\b" + re.escape(s.lower()) + r"\b", full_text)]
                skill_score = int((len(matched) / max(len(jd["skills"]), 1)) * 60)
                exp_score = 40 if (jd["min_exp"] <= exp_years <= jd["max_exp"]) else 25
                total_match = min(100, skill_score + exp_score)

                if total_match < min_score:
                    continue

                is_locked, lock_reason = check_vault_lockout(name, jd["client"])
                if fresh_only and is_locked:
                    continue

                comp = ""
                if " at " in role:
                    comp = role.split(" at ")[-1].strip()

                phone_raw, email_raw = extract_phone_and_email(f"{skills_raw} {name} {role}")
                radar_type, radar_label = evaluate_readiness(notice, role, skills_raw)
                parsed_skills = [s.strip() for s in skills_raw.replace("|;", ",").replace("|", ",").split(",") if s.strip() and len(s.strip()) < 35]
                li_url = row.get("LinkedIn_Search", f"https://www.google.com/search?q={name}+{comp}+site%3Alinkedin.com%2Fin")

                candidates.append({
                    "name": name,
                    "match_score": total_match,
                    "role": role,
                    "company": comp,
                    "exp": exp,
                    "location": loc or "Pan India",
                    "phone": phone_raw,
                    "email": email_raw,
                    "notice": notice,
                    "radar_type": radar_type,
                    "radar_label": radar_label,
                    "skills": parsed_skills[:6],
                    "matched_skills": matched,
                    "is_locked": is_locked,
                    "lock_reason": lock_reason or "",
                    "linkedin": li_url
                })

        candidates.sort(key=lambda x: x["match_score"], reverse=True)

        return jsonify({
            "success": True,
            "filename": os.path.basename(latest_file),
            "jd_title": jd_title,
            "candidates": candidates
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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

@app.route("/api/find-candidate-contact", methods=["GET"])
def api_find_candidate_contact():
    name = request.args.get("name", "").strip()
    company = request.args.get("company", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name required"})

    phone = ""
    email = ""
    linkedin = ""

    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            q = f'"{name}" "{company}" email OR phone OR contact OR resume OR gmail.com site:linkedin.com/in'
            results = list(ddgs.text(q, max_results=3))
            full_text = " ".join([r.get("title", "") + " " + r.get("body", "") for r in results])
            phone, email = extract_phone_and_email(full_text)
            for r in results:
                href = r.get("href", "")
                if "linkedin.com/in/" in href and not linkedin:
                    linkedin = href
    except Exception as e:
        pass

    return jsonify({
        "success": True,
        "name": name,
        "phone": phone or "Not found publicly",
        "email": email or "Not found publicly",
        "linkedin": linkedin
    })
