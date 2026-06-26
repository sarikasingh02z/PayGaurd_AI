
import re

# --- STATION 1: PII MASKER ---
# Masks sensitive identifiers before any data leaves the system

PHONE_REGEX = re.compile(r'(?:\+91[-\s]?)?\b[6-9]\d{9}\b')
AADHAAR_REGEX = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
EMAIL_REGEX = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
UPI_REGEX = re.compile(r'\b[\w.\-]+@[a-zA-Z]+\b')
PAN_REGEX = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
TRANSACTION_REF_REGEX = re.compile(r'\b[A-Z0-9]*[0-9][A-Z0-9]*\b(?=\s|$)')

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


samples = [
    "My UPI ID raj@okaxis was used for unauthorized transaction",
    "Transaction reference T2506251234567 failed yesterday",
    "My PAN ABCDE1234F was used without consent",
    "The payment was UNAUTHORIZED and amount got DEDUCTED",
    "SETTLEMENT pending since last week on my account",
    "Amount debited but not credited to merchant"
]

for s in samples:
    masked = mask_text(s)
    print(f"Original : {s}")
    print(f"Masked   : {masked}")
    print()