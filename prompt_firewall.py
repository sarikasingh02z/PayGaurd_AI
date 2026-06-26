import re

def validate_input(complaint_text):
    """
    Prompt Firewall: Sanitize input before it reaches the AI.
    Blocks prompt injection, oversized payloads, and malicious patterns.
    """
    if not complaint_text or not complaint_text.strip():
        return False, "Complaint text is empty."
    
    if len(complaint_text) > 1000:
        return False, "Complaint text is too long. Maximum 1000 characters allowed."
    
    #block prompt injection patterns
    injection_patterns = [
        "ignore previous instructions",
        "system prompt",
        "you are now",
        "disregard",
        "forget everything",
        "act as",
        "pretend to be",
        "jailbreak",
        "override instructions",
        "new instructions"
    ]
    for pattern in injection_patterns:
        if pattern in complaint_text.lower():
            return False, "Invalid input detected."
    
    #block control characters
    control_characters = ["\t", "\r", "\b", "\f", "\v"]
    for char in control_characters:
        if char in complaint_text:
            return False, "Invalid characters detected."
    
    # Sanitize
    sanitized_text = re.sub(r"[^a-zA-Z0-9\s\.,!?@₹/\-_]", "", complaint_text)
    
    #check if anything after sanitization
    if not sanitized_text.strip():
        return False, "Complaint text contains no valid content."
    
    return True, sanitized_text.strip()
