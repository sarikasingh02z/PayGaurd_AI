import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_ai_response(masked_complaint, tat_result):
    prompt = f"""You are a banking compliance officer AI assistant.
Analyze this customer complaint and compliance data.

Complaint: {masked_complaint}
Payment Category: {tat_result.get('payment_type', 'Unknown')}
TAT Deadline: {tat_result['tat_deadline']}
Overdue Days: {tat_result['overdue_days']}
Accrued Penalty: ₹{tat_result['accrued_penalty']}
Status: {tat_result['status']}

Respond ONLY in this exact JSON format, no markdown, no extra text:
{{
    "summary": "one sentence summary of the issue",
    "recommended_urgency": "HIGH or MEDIUM or LOW",
    "suggested_agent_script": "polished response template for the support agent"
}}"""

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
    return json.loads(raw.strip())

# Test
if __name__ == "__main__":
    test_complaint = "My payment failed and amount was deducted but not received"
    test_tat = {
        "payment_type": "Merchant",
        "tat_deadline": "2026-06-17",
        "overdue_days": 7,
        "accrued_penalty": 700,
        "status": "OPEN"
    }
    result = get_ai_response(test_complaint, test_tat)
    print(json.dumps(result, indent=2))