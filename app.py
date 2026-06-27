import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from masker import mask_text
from keyword_engine import classify_text, extract_merchant
from tat_clock import calculate_tat
from AI_orchestrator import get_ai_response
from database import initialize_db, insert_record, fetch_all_records
from prompt_firewall import validate_input

load_dotenv()
app = Flask(__name__)
CORS(app)
initialize_db()

# POST /api/audit
@app.route('/api/audit', methods=['POST'])
def audit():
    try:
        data = request.get_json()
        if not data or not data.get('complaint'):
            return jsonify({"error": "complaint field is required"}), 400
        raw_complaint = data.get('complaint', '').strip()
        payment_type = data.get('payment_type', 'Merchant')
        failure_date = data.get('failure_date', '2026-06-20')
        try:
            datetime.strptime(failure_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "failure_date must be in YYYY-MM-DD format"}), 400
        if not raw_complaint:
            return jsonify({"error": "complaint cannot be empty"}), 400

        #prompt_firewall
        is_valid, sanitized_text = validate_input(raw_complaint)
        if not is_valid:
            return jsonify({"error": sanitized_text}), 400

        #STATION 1 — PII Masking
        masked_complaint = mask_text(sanitized_text)

        #STATION 2 — Keyword Classification
        risk_category = classify_text(masked_complaint)

        merchant_name = extract_merchant(raw_complaint)

        #STATION 3 — TAT & Penalty Calculation
        tat_result = calculate_tat(payment_type, failure_date)
        tat_result['payment_type'] = payment_type

        #STATION 4 — AI Response Generation
        try:
            ai_result = get_ai_response(masked_complaint, tat_result)
        except Exception as ai_error:
            #default
            ai_result = {
                "summary": "Complaint received and logged for compliance review.",
                "recommended_urgency": "HIGH" if risk_category == "CRITICAL_FRAUD" else "MEDIUM",
                "suggested_agent_script": "Dear customer, your complaint has been received and escalated to our compliance team. We will resolve this within the RBI mandated timeline."
            }

        #STATION 5 — Save to Database
        record = {
            "raw_complaint": raw_complaint,
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
        record_id = insert_record(record)

        #full response
        return jsonify({
            "id": record_id,
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
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# GET /api/history
@app.route('/api/history', methods=['GET'])
def history():
    try:
        records = fetch_all_records()
        return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
