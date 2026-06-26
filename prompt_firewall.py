import re

def validate_input(complaint_text):
    
    if not complaint_text or not complaint_text.strip():
        return False, "Complaint text is empty."

    if len(complaint_text) > 1000:
        return False, "Complaint text is too long."

    # Check injection patterns
    injection_patterns = [
        "ignore previous instructions",
        "system prompt",
        "you are now",
        "disregard",
        "forget everything",
        "act as",
        "pretend to be"
    ]
    for pattern in injection_patterns:
        if pattern in complaint_text.lower():
            return False, "Complaint text contains a prompt injection pattern."

    # Check control characters and dangerous input
    control_characters = ["\t", "\r", "\b", "\f", "\v"]
    for character in control_characters:
        if character in complaint_text:
            return False, "Complaint text contains a control character."

    # Return sanitized text
    sanitized_text = re.sub(r"[^a-zA-Z0-9\s\.,!?-]", "", complaint_text)
    return True, sanitized_text.strip()


#Example 
if __name__ == "__main__":
    print(validate_input("This is a valid complaint text."))
    print(validate_input(""))
    print(validate_input("a" * 1001))
    print(validate_input("ignore previous instructions"))
    print(validate_input("Hello\nWorld"))

    
    is_valid, message_or_sanitized_text = validate_input("This is a valid complaint text.")
    if is_valid:
        print("Calling AI Orchestrator with sanitized text:")
        print(message_or_sanitized_text)
    else:
        print("Fallback response:")
        print(message_or_sanitized_text)