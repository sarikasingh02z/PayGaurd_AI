import streamlit as st
import pandas as pd
import random
import plotly.express as px
from datetime import datetime, timedelta
import re
import json
import sqlite3
import os
from groq import Groq

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- Page Config ---
st.set_page_config(page_title="PayGuard AI", layout="wide", page_icon="🛡️")

# --- CSS ---
st.markdown("""
    <style>
        .stApp { background-color: #0d0f14; color: #ffffff; }
        .stButton button { background-color: #CC2A49; color: white; border-radius: 8px; }
        div[data-testid="stMetricValue"] { font-size: 2rem; font-weight: bold; color: #ffffff; }
        h1, h2, h3 { color: #ffffff !important; }
        .stDataFrame { border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/security-checked--v1.png", width=60)
    st.title("🛡️ PayGuard AI")
    st.markdown("---")
    st.markdown("### RBI Compliance Engine")
    st.markdown("**Circular 67 (RBI/2019-20/67)**")
    st.markdown("• P2P Transfers: **T+1** working day")
    st.markdown("• Merchant Failures: **T+5** working days")
    st.markdown("• Penalty: **₹100/day** per complaint")
    st.markdown("---")
    page = st.radio("Navigate", [
        "Submit Complaint",
        "Complaint Replay",
        "Bank Compliance Monitor"
    ])
    st.markdown("---")

# ============================================================
# BACKEND LOGIC
# ============================================================

# --- 1. PII Masker ---
PHONE_REGEX = re.compile(r'(?:\+91[-\s]?)?\b[6-9]\d{9}\b')
AADHAAR_REGEX = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
EMAIL_REGEX = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
UPI_REGEX = re.compile(r'\b[\w.\-]+@[a-zA-Z]+\b')
PAN_REGEX = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
TRANSACTION_REF_REGEX = re.compile(r'\b(?:TXN|REF|ORD|RRN|UTR)[A-Z0-9]{6,}\b', re.IGNORECASE)

def mask_text(text):
    if not text or not text.strip():
        return text
    text = PHONE_REGEX.sub('[REDACTED]', text)
    text = AADHAAR_REGEX.sub('[REDACTED]', text)
    text = EMAIL_REGEX.sub('[REDACTED]', text)
    text = PAN_REGEX.sub('[REDACTED]', text)
    text = UPI_REGEX.sub('[REDACTED]', text)
    text = TRANSACTION_REF_REGEX.sub('[REDACTED]', text)
    return text

# --- 2. Keyword Classification ---
CRITICAL_FRAUD_PATTERNS = [
    r"(unauthorized|fraud|scam|hacked)\s+(transaction|debit|credit|payment|transfer)",
    r"(not\s+done\s+by\s+me|not\s+my\s+transaction)",
    r"otp\s+(shared|given|sent)",
    r"unknown\s+(transaction|debit|credit)",
    r"(account|card|upi)\s+(hacked|compromised|breached)",
    r"(fraud|fake|scam|phishing|cheat|stolen|compromised)",
    r"money\s+mule",
    r"suspicious\s+(transfer|transaction|activity),"
    r"card\s+(cloned|skimmed|stolen)",
    r"atm\s+(fraud|cloned|skimmed|withdrawn)",
    r"withdrawn.*different\s+city",
    r"not\s+done\s+by\s+me",
    r"\bhacked\b",
    r"without\s+my\s+knowledge",
    r"\bscam\b",
    r"\bunauthorized\b",
    r"phishing\s+(link|email|call|sms)",
    r"cyber\s+(fraud|crime|attack)",
    r"social\s+engineering",
    r"impersonation",
    r"account\s+(takeover|compromised)",
    r"upi\s+(fraud|scam|fake)"
]

TECHNICAL_GLITCH_KEYWORDS = [
    "timed out", "declined", "amount deducted", "server down",
    "settlement", "failed", "stuck", "debited", "not received",
    "pending", "error", "transaction failed", "double deduction",
    "refund not received", "upi failed", "money deducted",
    "not credited", "payment stuck", "deducted twice",
    "transaction timed out", "gateway error", "network issue",
    "technical glitch", "system error", "payment declined",
    "transaction declined", "amount not credited", "refund pending",
    "settlement pending", "processing error", "connection error",
    "bank server down", "payment gateway error", "upi error",
    "transaction pending", "duplicate transaction", "partial deduction",
    "amount debited but not settled", "ticket not generated",
    "order not placed", "payment not successful"
]

KNOWN_MERCHANTS = [
    "flipkart", "amazon", "swiggy", "zomato", "myntra", "paytm",
    "phonepe", "gpay", "google pay", "uber", "ola",
    "makemytrip", "irctc", "netflix", "zepto", "blinkit",
    "meesho", "nykaa", "bigbasket"
]

def classify_text(masked_text):
    if not masked_text or not masked_text.strip():
        return "UNKNOWN"
    text_lower = masked_text.lower()
    
    general_patterns = [
        "i need", "i want", "can you", "could you", "please help",
        "help me", "transaction receipt", "balance", "statement",
        "passbook", "upi limit", "daily limit", "limit was reduced",
        "transaction limit", "request for", "clarify", "explain",
        "understand why", "want to know", "need to know", "asking for",
        "receipt"
    ]
    
    for pattern in general_patterns:
        if pattern in text_lower:
            return "GENERAL"
    
    for pattern in CRITICAL_FRAUD_PATTERNS:
        if re.search(pattern, text_lower):
            return "CRITICAL_FRAUD"
    
    for keyword in TECHNICAL_GLITCH_KEYWORDS:
        if keyword in text_lower:
            return "TECHNICAL_GLITCH"
    
    return "GENERAL"

def extract_merchant(complaint_text):
    text_lower = complaint_text.lower()
    for merchant in KNOWN_MERCHANTS:
        if merchant in text_lower:
            return merchant.title()
    return "Unknown Merchant"

# --- 3. TAT Clock ---
def calculate_tat(payment_type, failure_date_str):
    failure_date = datetime.strptime(failure_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    working_days_allowed = 1 if payment_type == "P2P" else 5
    current = failure_date
    days_added = 0
    while days_added < working_days_allowed:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days_added += 1
    deadline = current
    if today > deadline:
        overdue_days = (today - deadline).days
        penalty = overdue_days * 100
        status = "BREACHED"
    else:
        overdue_days = 0
        penalty = 0
        status = "IN_PROGRESS"
    return {
        "complaint_age_days": (today - failure_date).days,
        "tat_deadline": deadline.strftime("%Y-%m-%d"),
        "overdue_days": overdue_days,
        "accrued_penalty": penalty,
        "status": status
    }

# --- 4. Prompt Firewall ---
def validate_input(complaint_text):
    if not complaint_text or not complaint_text.strip():
        return False, "Complaint text is empty."
    
    if len(complaint_text) > 1000:
        return False, "Complaint text is too long. Maximum 1000 characters allowed."
    
    injection_patterns = [
        "ignore previous instructions", "system prompt", "you are now",
        "disregard", "forget everything", "act as", "pretend to be",
        "jailbreak", "override instructions", "new instructions"
    ]
    for pattern in injection_patterns:
        if pattern in complaint_text.lower():
            return False, "Invalid input detected."
    
    control_characters = ["\t", "\r", "\b", "\f", "\v"]
    for char in control_characters:
        if char in complaint_text:
            return False, "Invalid characters detected."
    
    sanitized_text = re.sub(r"[^a-zA-Z0-9\s\.,!?@₹/\-_]", "", complaint_text)
    
    if not sanitized_text.strip():
        return False, "Complaint text contains no valid content."
    
    words = re.findall(r'\b[a-zA-Z]{3,}\b', sanitized_text)
    unique_words = set(words)
    filler_words = {
        'the', 'and', 'for', 'you', 'was', 'are', 'not', 'but', 'has', 
        'have', 'with', 'can', 'had', 'too', 'via', 'one', 'get', 'use',
        'due', 'now', 'yet', 'may', 'its', 'all', 'any', 'own', 'new',
        'day', 'way', 'say', 'see', 'try', 'let', 'did', 'ask', 'us',
        'help', 'please', 'need', 'want', 'get'
    }
    meaningful_words = [w for w in unique_words if w.lower() not in filler_words]
    
    def is_valid_word(word):
        if len(word) < 4:
            return False
        if re.search(r'(.)\1{3,}', word):
            return False
        return True
    
    meaningful_words = [w for w in meaningful_words if is_valid_word(w)]
    
    if len(meaningful_words) < 5:
        return False, "Please provide a clear complaint description with at least 5 meaningful words. We couldn't understand your issue."
    
    return True, sanitized_text.strip()

# --- 5. AI Orchestrator (GROQ) ---
def get_ai_response(masked_complaint, tat_result, risk_category=None):
    """
    Get AI response from Groq with urgency override based on risk category.
    """
    
    prompt = f"""You are a neutral compliance assistant analyzing a customer complaint. You do NOT represent the bank or any specific institution. Your job is to analyze the complaint and provide objective summaries and suggested responses.

Analyze this customer complaint and compliance data.

Complaint: {masked_complaint}
Payment Category: {tat_result.get('payment_type', 'Unknown')}
TAT Deadline: {tat_result['tat_deadline']}
Overdue Days: {tat_result['overdue_days']}
Accrued Penalty: ₹{tat_result['accrued_penalty']}

IMPORTANT URGENCY RULES:
- If the complaint is about fraud, hacking, unauthorized transaction, or OTP sharing → urgency is HIGH
- If the complaint is about technical issues, payment failure, or transaction stuck → urgency is MEDIUM
- If the complaint is about balance inquiry, receipt request, limit query, or general help → urgency is LOW
- If overdue days > 5 or penalty > ₹500 → urgency can be HIGH regardless

Respond ONLY in this exact JSON format, no markdown, no extra text:
{{
    "summary": "one sentence summary of the issue",
    "recommended_urgency": "HIGH or MEDIUM or LOW",
    "suggested_agent_script": "polished response template for the support agent"
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        ai_result = json.loads(raw.strip())
        
        # SMART OVERRIDE — Based on risk category
        if risk_category == "CRITICAL_FRAUD":
            ai_result["recommended_urgency"] = "HIGH"
        elif risk_category == "TECHNICAL_GLITCH":
            if tat_result.get('overdue_days', 0) > 5 or tat_result.get('accrued_penalty', 0) > 500:
                ai_result["recommended_urgency"] = "HIGH"
            else:
                ai_result["recommended_urgency"] = "MEDIUM"
        elif risk_category == "GENERAL":
            ai_result["recommended_urgency"] = "LOW"
        
        return ai_result
        
    except Exception as e:
        print(f"Groq API error: {e}")
        # FALLBACK — Rule-based if Groq fails
        if risk_category == "CRITICAL_FRAUD":
            return {
                "summary": "Customer reported a potential fraud incident.",
                "recommended_urgency": "HIGH",
                "suggested_agent_script": "Dear customer, we have escalated your fraud complaint to our security team. Please share any transaction IDs or screenshots to help us investigate quickly."
            }
        elif risk_category == "TECHNICAL_GLITCH":
            urgency = "HIGH" if tat_result.get('overdue_days', 0) > 5 else "MEDIUM"
            return {
                "summary": "Customer reported a technical payment failure.",
                "recommended_urgency": urgency,
                "suggested_agent_script": "Dear customer, we are investigating the payment failure issue. We will update you within 24 hours."
            }
        else:
            return {
                "summary": "Customer submitted a general query.",
                "recommended_urgency": "LOW",
                "suggested_agent_script": "Dear customer, we have received your request and will get back to you within 2 working days."
            }

# --- 6. Database (SQLite) ---
DB_PATH = "enterprise_compliance.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compliance_ledger (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_complaint       TEXT NOT NULL,
            masked_complaint    TEXT NOT NULL,
            risk_category       TEXT NOT NULL,
            tat_deadline        TEXT NOT NULL,
            accrued_penalty     INTEGER DEFAULT 0,
            complaint_age_days  INTEGER DEFAULT 0,
            overdue_days        INTEGER DEFAULT 0,
            status              TEXT DEFAULT 'OPEN',
            ai_summary          TEXT,
            ai_urgency          TEXT,
            agent_script        TEXT,
            merchant_name       TEXT DEFAULT 'Unknown Merchant',
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def insert_record(data):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO compliance_ledger (
                raw_complaint, masked_complaint, risk_category,
                tat_deadline, accrued_penalty, complaint_age_days,
                overdue_days, status, ai_summary, ai_urgency,
                agent_script, merchant_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get("raw_complaint"),
            data.get("masked_complaint"),
            data.get("risk_category"),
            data.get("tat_deadline"),
            data.get("accrued_penalty", 0),
            data.get("complaint_age_days", 0),
            data.get("overdue_days", 0),
            data.get("status", "OPEN"),
            data.get("ai_summary"),
            data.get("ai_urgency"),
            data.get("agent_script"),
            data.get("merchant_name", "Unknown Merchant")
        ))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Database insert error: {e}")
        return None
    finally:
        conn.close()

def fetch_all_records():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT * FROM compliance_ledger
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Database fetch error: {e}")
        return []
    finally:
        conn.close()

# --- 7. Main Processing Function ---
def generate_complaint_id():
    return f"CMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def process_complaint(complaint_text, payment_type, failure_date):
    masked_complaint = mask_text(complaint_text)
    risk_category = classify_text(masked_complaint)
    merchant_name = extract_merchant(complaint_text)
    
    is_valid, sanitized_text = validate_input(complaint_text)
    if not is_valid:
        return None, sanitized_text
    
    tat_result = calculate_tat(payment_type, failure_date)
    tat_result['payment_type'] = payment_type
    
    if risk_category == "GENERAL":
        tat_result['status'] = "RESOLVED"
    elif tat_result['status'] == "BREACHED":
        pass
    else:
        tat_result['status'] = "IN_PROGRESS"
    
    ai_result = get_ai_response(masked_complaint, tat_result, risk_category)
    
    complaint_id = generate_complaint_id()
    
    record = {
        "raw_complaint": complaint_text,
        "masked_complaint": masked_complaint,
        "risk_category": risk_category,
        "tat_deadline": tat_result['tat_deadline'],
        "accrued_penalty": tat_result['accrued_penalty'],
        "complaint_age_days": tat_result['complaint_age_days'],
        "overdue_days": tat_result['overdue_days'],
        "status": tat_result['status'],
        "ai_summary": ai_result['summary'],
        "ai_urgency": ai_result['recommended_urgency'],
        "agent_script": ai_result['suggested_agent_script'],
        "merchant_name": merchant_name
    }
    insert_record(record)
    
    return {
        "id": complaint_id,
        "masked_complaint": masked_complaint,
        "risk_category": risk_category,
        "merchant_name": merchant_name,
        "tat_deadline": tat_result['tat_deadline'],
        "complaint_age_days": tat_result['complaint_age_days'],
        "overdue_days": tat_result['overdue_days'],
        "accrued_penalty": tat_result['accrued_penalty'],
        "status": tat_result['status'],
        "ai_summary": ai_result['summary'],
        "ai_urgency": ai_result['recommended_urgency'],
        "agent_script": ai_result['suggested_agent_script']
    }, None

# ============================================================
# INITIALIZE DATABASE
# ============================================================
initialize_db()
records = fetch_all_records()

# ============================================================
# PAGE 1 — SUBMIT COMPLAINT
# ============================================================
if page == "Submit Complaint":
    st.subheader("Submit a Complaint")
    st.caption("Complaint runs through all 5 stations automatically")

    col1, col2 = st.columns([3, 1])
    with col1:
        complaint_text = st.text_area(
            "Complaint Description",
            height=150,
            placeholder="Type your complaint here"
        )
    with col2:
        payment_type = st.selectbox("Payment Type", ["P2P", "Merchant"])
        failure_date = st.date_input("Failure Date", datetime.now().date())
        submit_btn = st.button(
            "Run Compliance Audit",
            type="primary",
            use_container_width=True
        )

    st.markdown("---")
    st.caption("Or select a sample complaint:")
    
    sample_data = [
        "My UPI payment of Rs 5000 to Flipkart failed. Amount deducted but not received.",
        "Unauthorized transaction of Rs 15000 from my account. OTP was shared unknowingly.",
        "I need a copy of my transaction receipt. Email me at test@gmail.com.",
        "My bank passbook and UPI history showing different balance. Need help understanding.",
        "Card cloned at ATM. Rs 28000 withdrawn from different city while I was at home.",
        "Payment to Amazon failed but amount of Rs 3200 was deducted.",
        "UPI transaction timed out but money got deducted. Transaction shows failed.",
        "Someone hacked my UPI ID and transferred Rs 8000 without my knowledge.",
        "Double payment charged on Flipkart. Rs 1299 debited twice.",
        "My PAN was used for a transaction I never made. Fraud transaction of Rs 12000.",
    ]
    
    selected_sample = st.selectbox("", ["Select a sample complaint"] + sample_data)
    
    if selected_sample and selected_sample != "Select a sample complaint":
        complaint_text = selected_sample

    if submit_btn and complaint_text:
        with st.spinner("Processing through 5 stations..."):
            result, error = process_complaint(
                complaint_text,
                payment_type,
                failure_date.strftime("%Y-%m-%d")
            )
            if error:
                st.error(f"Error: {error}")
            else:
                st.session_state['last_result'] = result
                st.success("Complaint processed successfully!")
                st.rerun()

    if 'last_result' in st.session_state:
        result = st.session_state['last_result']
        st.markdown("---")
        
        st.subheader("5-Station Pipeline")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.success("Station 1\nPII Masking")
        
        risk = result.get('risk_category', 'N/A')
        if risk == 'CRITICAL_FRAUD':
            c2.error(f"Station 2\nClassification:\n {risk}")
        elif risk == 'TECHNICAL_GLITCH':
            c2.warning(f"Station 2\nClassification:\n {risk}")
        else:
            c2.success(f"Station 2\nClassification:\n {risk}")
        
        c3.success("Station 3\nPrompt Firewall:\n Passed")
        
        status = result.get('status', 'OPEN')
        penalty = result.get('accrued_penalty', 0)
        if status == 'BREACHED':
            c4.error(f"Station 4\nTAT Clock\n BREACHED\n₹{penalty} penalty")
        elif status == 'OPEN':
            c4.warning("Station 4\nTAT Clock:\n OPEN")
        else:
            c4.success(f"Station 4\nTAT Clock:\n {status}")
        
        urgency = result.get('ai_urgency', 'N/A')
        if urgency == 'HIGH':
            c5.error(f"Station 5\nAI Orchestrator:\n {urgency}")
        elif urgency == 'MEDIUM':
            c5.warning(f"Station 5\nAI Orchestrator:\n {urgency}")
        else:
            c5.success(f"Station 5\nAI Orchestrator:\n {urgency}")

        st.markdown("---")

        col_a, col_b = st.columns(2)
        with col_a:
            ticket_id = result.get('id', 'N/A')
            st.markdown(f"**Ticket ID:** `#{ticket_id if ticket_id else 'N/A'}`")
            st.markdown(f"**Risk Category:** `{result.get('risk_category', 'N/A')}`")
            st.markdown(f"**AI Urgency:** `{result.get('ai_urgency', 'N/A')}`")
            st.markdown(f"**Status:** `{result.get('status', 'OPEN')}`")
            st.markdown(f"**TAT Deadline:** `{result.get('tat_deadline', 'N/A')}`")
            st.markdown(f"**Overdue Days:** `{result.get('overdue_days', 0)}`")
            st.markdown(f"**Accrued Penalty:** `₹{result.get('accrued_penalty', 0)}`")

        with col_b:
            st.markdown("**Masked Complaint:**")
            masked = result.get('masked_complaint', '')
            st.info(masked)
            st.markdown("**AI Summary:**")
            st.write(result.get('ai_summary', 'N/A'))

        st.markdown("**Agent Script:**")
        st.text_area("Copy this response:", result.get('agent_script', ''), height=100)

        if st.button("Clear Result"):
            if 'last_result' in st.session_state:
                del st.session_state['last_result']
                st.rerun()

# ============================================================
# PAGE 2 — COMPLAINT REPLAY
# ============================================================
elif page == "Complaint Replay":
    st.subheader("Complaint Replay — 5-Station Pipeline Viewer")
    st.caption("Select any past complaint to see exactly how it was processed")

    if records:
        options = {
            f"#{r.get('id', 'N/A')} | {r.get('merchant_name', 'Unknown')} | {r.get('risk_category', '')} | ₹{r.get('accrued_penalty', 0)}": r
            for r in records
        }
        selected_label = st.selectbox("Select Complaint", list(options.keys()))
        selected = options[selected_label]
        st.markdown("---")

        st.markdown("### Station 1 — PII Redaction")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Original Complaint:**")
            st.warning(selected.get('raw_complaint', 'N/A'))
        with col2:
            st.markdown("**After Masking:**")
            masked = selected.get('masked_complaint', 'N/A')
            st.error(masked)
            
        st.markdown("---")

        st.markdown("### Station 2 — Keyword Classification")
        risk = selected.get('risk_category', 'N/A')
        if risk == 'CRITICAL_FRAUD':
            st.error(f"{risk} — Escalated for immediate action")
        elif risk == 'TECHNICAL_GLITCH':
            st.warning(f"{risk} — Payment failure detected")
        else:
            st.success(f"{risk} — Routine query")

        st.markdown("---")

        st.markdown("### Station 3 — Prompt Firewall")
        st.success("Input validated — No injection detected")

        st.markdown("---")

        st.markdown("### Station 4 — RBI TAT Clock")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("TAT Deadline", selected.get('tat_deadline', 'N/A'))
        col2.metric("Complaint Age", f"{selected.get('complaint_age_days', 0)} days")
        col3.metric("Overdue Days", selected.get('overdue_days', 0))
        col4.metric("Penalty", f"₹{selected.get('accrued_penalty', 0)}")

        status = selected.get('status')
        if status == 'BREACHED':
            st.error("BREACHED — RBI Deadline Missed — Penalty Accruing")
        elif status == 'OPEN':
            st.warning("OPEN — Within RBI Deadline")
        else:
            st.success("RESOLVED — Routine Query Closed")

        st.markdown("---")

        st.markdown("### Station 5 — AI Orchestrator")
        col1, col2 = st.columns(2)
        with col1:
            urgency = selected.get('ai_urgency', 'N/A')
            if urgency == 'HIGH':
                st.error(f"Urgency: {urgency}")
            elif urgency == 'MEDIUM':
                st.warning(f"Urgency: {urgency}")
            else:
                st.success(f"Urgency: {urgency}")
            st.markdown("**AI Summary:**")
            st.write(selected.get('ai_summary', 'N/A'))
        with col2:
            st.markdown("**Agent Script:**")
            st.text_area("", selected.get('agent_script', 'N/A'), height=150, disabled=True)
    else:
        st.info("No complaints available. Submit one first.")

# ============================================================
# PAGE 3 — BANK COMPLIANCE MONITOR
# ============================================================
elif page == "Bank Compliance Monitor":
    st.title("Bank Compliance Monitor")
    st.caption("Hypothetical scenario modeling — RBI TAT breach impact on penalty exposure")

    st.markdown("""
    <div style="background-color: #1a1a2e; padding: 15px; border-radius: 8px; border-left: 4px solid #F99E4C; margin-bottom: 20px;">
        <p style="color: #F99E4C; margin: 0; font-weight: bold;"> Important Note on Data Presentation</p>
        <p style="color: #cccccc; margin: 5px 0 0 0; font-size: 0.9rem;">
            The bank names, daily disputed transaction volumes, and breach percentages shown on this page are <strong>entirely hypothetical</strong> generated solely to illustrate the penalty calculation logic.
            <br><br>
            <strong>What is real:</strong> The ₹100/day penalty rule, T+1 (P2P) and T+5 (Merchant) deadlines, and the mathematical formulas used to compute penalty exposure — all derived directly from RBI Circular 67.
            <br><br>
            <strong>What is simulated:</strong> The transaction volumes, breach rates, and bank labels. These are illustrative scenarios, not actual institutional data.
        </p>
    </div>
    """, unsafe_allow_html=True)

    @st.cache_data
    def generate_simulated_data():
        banks = ['SBI', 'HDFC', 'ICICI', 'Axis']
        data = {}
        for bank in banks:
            data[bank] = random.randint(50000, 150000)
        return data

    daily_disputed = st.session_state.get('daily_disputed') or generate_simulated_data()
    st.session_state['daily_disputed'] = daily_disputed

    selected_bank = st.selectbox("Select Bank", list(daily_disputed.keys()))
    base_volume = daily_disputed[selected_bank]

    st.markdown("---")
    st.subheader("Current State")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Daily Disputed Transactions (count)", f"{base_volume:,}")
        st.caption("Transactions that fail or get disputed — not total bank volume")
    with col2:
        current_breach_rate = st.slider(
            "Current Breach Rate (%)",
            min_value=1, max_value=20, value=8,
            help="What % of disputed transactions currently breach the RBI TAT deadline?"
        )

    avg_overdue_days = st.slider(
        "Average Days Overdue (before resolution)",
        min_value=1, max_value=10, value=3,
        help="On average, how many days late are breached complaints resolved?"
    )

    current_breaches = int(base_volume * (current_breach_rate / 100))
    current_daily_penalty = current_breaches * 100 * avg_overdue_days
    current_monthly_penalty = current_daily_penalty * 30

    p2p_breaches = int(current_breaches * 0.55)
    merchant_breaches = current_breaches - p2p_breaches

    col1, col2, col3 = st.columns(3)
    col1.metric("Breached Transactions/Day", f"{current_breaches:,}")
    col2.metric("Daily Penalty Exposure", f"₹{current_daily_penalty:,}")
    col3.metric("Monthly Penalty Exposure", f"₹{current_monthly_penalty:,}")

    st.markdown("---")

    st.subheader("Breach Split by Transaction Type")
    type_df = pd.DataFrame({
        'Type': ['P2P (T+1 deadline)', 'Merchant Gateway (T+5 deadline)'],
        'Breaches per Day': [p2p_breaches, merchant_breaches]
    })
    fig_bar = px.bar(type_df, x='Type', y='Breaches per Day', color='Type',
                      color_discrete_sequence=['#1ABC9C', '#E74C3C'], text='Breaches per Day')
    fig_bar.update_traces(textposition='outside')
    fig_bar.update_layout(showlegend=False)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    st.subheader("What-If: Fix vs. Ignore")
    st.write("Compare monthly penalty exposure if the bank improves resolution speed vs. lets it worsen.")

    improved_rate = max(1, current_breach_rate - 5)
    worsened_rate = min(20, current_breach_rate + 5)

    improved_breaches = int(base_volume * (improved_rate / 100))
    worsened_breaches = int(base_volume * (worsened_rate / 100))

    improved_penalty = improved_breaches * 100 * max(1, avg_overdue_days - 1) * 30
    worsened_penalty = worsened_breaches * 100 * (avg_overdue_days + 1) * 30

    scenario_df = pd.DataFrame({
        'Scenario': [
            f'If Improved (-5%, faster resolution)',
            f'Current ({current_breach_rate}%, {avg_overdue_days}d avg)',
            f'If Worsened (+5%, slower resolution)'
        ],
        'Monthly Penalty (₹)': [improved_penalty, current_monthly_penalty, worsened_penalty]
    })

    fig_scenario = px.bar(
        scenario_df, x='Scenario', y='Monthly Penalty (₹)',
        color='Scenario',
        color_discrete_sequence=['#1ABC9C', '#F39C12','#E74C3C'],
        text='Monthly Penalty (₹)'
    )
    fig_scenario.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
    fig_scenario.update_layout(showlegend=False, yaxis_title="Monthly Penalty Exposure (₹)")
    st.plotly_chart(fig_scenario, use_container_width=True)

    savings_if_improved = current_monthly_penalty - improved_penalty
    cost_if_worsened = worsened_penalty - current_monthly_penalty

    col1, col2 = st.columns(2)
    col1.success(f"**Improving** resolution speed saves **₹{savings_if_improved:,}/month**")
    col2.error(f"**Ignoring** the problem costs an extra **₹{cost_if_worsened:,}/month**")

    st.markdown("---")
    st.caption("All figures are illustrative scenarios based on adjustable assumptions, not real bank data.")

st.markdown("---")
st.caption("PayGuard AI — RBI Circular 67 Compliance Engine")
