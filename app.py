import os
import json
import sqlite3
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), 'jobintel.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            salary TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT NOT NULL,
            required_skills TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            job_id TEXT,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            stage TEXT NOT NULL,
            ats_score INTEGER DEFAULT 0,
            interview_score INTEGER DEFAULT 0,
            feedback TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Seed default Jobs
    cursor.execute('SELECT COUNT(*) FROM jobs')
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO jobs (id, title, company, location, salary, type, description, required_skills)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ('job-1', 'Full Stack SDE (Python/React)', 'Google Cloud', 'Bengaluru / Remote', '₹24 - ₹32 LPA', 'Full-Time', 'Architect scalable cloud platforms and WebRTC assessment streaming layers.', 'Python, Flask, React.js, WebRTC, SQL, REST APIs'),
            ('job-2', 'Backend Systems Engineer', 'Microsoft Core', 'Hyderabad', '₹22 - ₹28 LPA', 'Full-Time', 'Build high-throughput distributed microservices and database clustering.', 'Python, Flask, Docker, PostgreSQL, Concurrency, Redis'),
            ('job-3', 'Cloud Infrastructure Engineer', 'Amazon AWS', 'Bengaluru', '₹20 - ₹26 LPA', 'Full-Time', 'Design resilient event-driven architectures and manage automated container pipelines.', 'Python, Linux, AWS, CI/CD, Docker, Microservices'),
            ('job-4', 'API Infrastructure Developer', 'Stripe Payments', 'Bengaluru / Hybrid', '₹28 - ₹36 LPA', 'Full-Time', 'Scale mission-critical low-latency financial transaction webhooks.', 'Python, Flask, SQL, WebSockets, System Design, REST APIs')
        ])

    # Seed default Pipeline Applications
    cursor.execute('SELECT COUNT(*) FROM applications')
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO applications (id, job_id, company, role, stage, ats_score, interview_score, feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ('app-1', 'job-1', 'Google Cloud', 'Full Stack SDE (Python/React)', 'Technical Assessment', 92, 88, 'ATS cleared with 92% match. Eligible for live AI proctored studio.'),
            ('app-2', 'job-2', 'Microsoft Core', 'Backend Systems Engineer', 'Online Assessment (OA)', 89, 0, 'CodeSignal OA pending submission.'),
            ('app-3', 'job-3', 'Amazon AWS', 'Cloud Infrastructure Engineer', 'Resume Screening', 76, 0, 'Automated NLP resume screening in progress.'),
            ('app-4', 'job-4', 'Stripe Payments', 'API Infrastructure Developer', 'Applied', 84, 0, 'Application submitted with verified resume credentials.')
        ])

    conn.commit()
    conn.close()

init_db()

# --- JOB BOARD ENDPOINTS ---
@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, company, location, salary, type, description, required_skills FROM jobs')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([
        {"id": r[0], "title": r[1], "company": r[2], "location": r[3], "salary": r[4], "type": r[5], "description": r[6], "required_skills": r[7]}
        for r in rows
    ])

# --- PIPELINE ENDPOINTS ---
@app.route('/api/pipeline', methods=['GET'])
def get_pipeline():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, job_id, company, role, stage, ats_score, interview_score, feedback FROM applications ORDER BY updated_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([
        {"id": r[0], "job_id": r[1], "company": r[2], "role": r[3], "stage": r[4], "ats_score": r[5], "interview_score": r[6], "feedback": r[7]}
        for r in rows
    ])

@app.route('/api/apply', methods=['POST'])
def apply_job():
    data = request.get_json() or {}
    job_id = data.get('jobId')
    company = data.get('company', 'Tech Enterprise')
    role = data.get('role', 'Software Engineer')
    ats_score = data.get('atsScore', 85)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    new_id = f"app-{os.urandom(3).hex()}"
    cursor.execute("""
        INSERT INTO applications (id, job_id, company, role, stage, ats_score, interview_score, feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (new_id, job_id, company, role, 'Applied', ats_score, 0, 'Direct 1-Click Application submitted with JobIntel ATS Resume.'))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "applicationId": new_id})

@app.route('/api/pipeline/update-stage', methods=['POST'])
def update_stage():
    data = request.get_json() or {}
    cand_id = data.get('candidateId')
    new_stage = data.get('stage')
    score = data.get('score', 92)
    feedback = data.get('feedback', 'Advanced following evaluation.')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE applications 
        SET stage = ?, interview_score = ?, feedback = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_stage, score, feedback, cand_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "candidateId": cand_id, "newStage": new_stage})

# --- ATS RESUME CHECKER ENDPOINT ---
@app.route('/api/ats/check', methods=['POST'])
def check_ats():
    data = request.get_json() or {}
    resume_text = data.get('resumeText', '').lower()
    job_desc = data.get('jobDescription', '').lower()

    if not resume_text:
        return jsonify({"error": "Resume text is empty"}), 400

    target_keywords = [
        'python', 'flask', 'react', 'webrtc', 'rest api', 'sql', 'sqlite', 'docker', 
        'concurrency', 'data structures', 'algorithms', 'git', 'oop', 'microservices'
    ]
    
    found_keywords = [kw for kw in target_keywords if kw in resume_text]
    missing_keywords = [kw for kw in target_keywords if kw not in resume_text]
    
    score = int((len(found_keywords) / len(target_keywords)) * 100)
    score = min(max(score, 45), 98)

    return jsonify({
        "atsScore": score,
        "matchedCount": len(found_keywords),
        "totalKeywords": len(target_keywords),
        "foundKeywords": found_keywords,
        "missingKeywords": missing_keywords,
        "analysis": f"Candidate profile matches {score}% of high-priority recruiter benchmarks.",
        "readabilityScore": "High (ATS-100 compliant layout)"
    })

# --- AI INTERVIEW STUDIO QUESTIONS ---
INTERVIEW_QUESTIONS = [
    {
        "index": 0,
        "question": "Welcome, Manvardhan. Let's inspect your JobIntel platform. How did you architect the WebRTC signaling layer between the client browser and your Flask backend to manage video streams, ICE candidate handshakes, and network dropouts?",
        "topic": "WebRTC Signaling & Concurrency"
    },
    {
        "index": 1,
        "question": "In your Flask backend for the 5-stage recruitment pipeline, how did you structure SQLite transactions and API endpoints to prevent race conditions when updating candidate statuses under concurrent access?",
        "topic": "Backend Concurrency & Transactional Integrity"
    },
    {
        "index": 2,
        "question": "Regarding the React client in JobIntel, how do you handle memory cleanup for active media streams and Web Audio Analyser nodes to prevent browser memory leaks when switching between dashboard stages?",
        "topic": "React Lifecycle & Media Resource Cleanup"
    },
    {
        "index": 3,
        "question": "In your AI Resume Screener project, what indexing and data structures did you utilize to ensure sub-100 millisecond response times when ranking high volumes of candidate data against role keywords?",
        "topic": "Data Modeling & Query Indexing"
    }
]

@app.route('/api/interview/next-question', methods=['POST'])
def next_question():
    data = request.get_json() or {}
    idx = data.get('questionIndex', 0)

    if idx >= len(INTERVIEW_QUESTIONS):
        return jsonify({
            "isFinished": True,
            "finalScore": 92,
            "evaluationSummary": "Strong architectural explanations of WebRTC media signaling and Flask microservices."
        })

    next_q = INTERVIEW_QUESTIONS[idx]
    return jsonify({
        "isFinished": False,
        "question": next_q["question"],
        "topic": next_q["topic"],
        "questionIndex": idx
    })

# Static SPA route
@app.route('/')
@app.route('/interview-studio')
def serve_app():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
