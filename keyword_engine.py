import re

CRITICAL_FRAUD_PATTERNS = [
    r"(unauthorized|fraud|scam|hacked)\s+(transaction|debit|credit|payment|transfer)",
    r"(not\s+done\s+by\s+me|not\s+my\s+transaction)",
    r"otp\s+(shared|given|sent)",
    r"unknown\s+(transaction|debit|credit)",
    r"(account|card|upi)\s+(hacked|compromised|breached)",
    r"(fraud|fake|scam|phishing|cheat|stolen|compromised)",
    r"money\s+mule",
    r"suspicious\s+(transfer|transaction|activity)"
]

TECHNICAL_GLITCH_KEYWORDS = [
    "timed out", "declined", "amount deducted", "server down",
    "settlement", "failed", "stuck", "debited", "not received",
    "pending", "error", "transaction failed", "double deduction",
    "refund not received", "upi failed", "money deducted",
    "not credited", "payment stuck", "deducted twice"
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
    
    #check fraud
    for pattern in CRITICAL_FRAUD_PATTERNS:
        if re.search(pattern, text_lower):
            return "CRITICAL_FRAUD"
    
    #check technical glitch 
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
