from datetime import datetime, timedelta

def calculate_tat(payment_type, failure_date_str):
    """
    Calculates RBI Circular 67 TAT and penalty accrual.
    Args:
        payment_type: "P2P" (T+1) or "Merchant" (T+5)
        failure_date_str: "YYYY-MM-DD" format
    Returns:
        dict: deadline, overdue_days, accrued_penalty, status, complaint_age
    """
    failure_date = datetime.strptime(failure_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()

    # working days allowed per RBI Circular 67
    working_days_allowed = 1 if payment_type == "P2P" else 5

    # Calculate deadline skipping weekends
    current = failure_date
    days_added = 0
    while days_added < working_days_allowed:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0, Friday=4
            days_added += 1
    deadline = current

    # Calculate penalty and status
    if today > deadline:
        overdue_days = (today - deadline).days
        penalty = overdue_days * 100
        status = "OPEN"
    else:
        overdue_days = 0
        penalty = 0
        status = "RESOLVED"

    return {
        "complaint_age_days": (today - failure_date).days,
        "tat_deadline": deadline.strftime("%Y-%m-%d"),
        "overdue_days": overdue_days,
        "accrued_penalty": penalty,
        "status": status
    }

# Test
print(calculate_tat("P2P", "2026-06-20"))
print(calculate_tat("Merchant", "2026-06-10"))
print(calculate_tat("Merchant", "2026-06-23"))