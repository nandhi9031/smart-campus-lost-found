import re


def analyze_report(
    report_type,
    title,
    description,
    category,
    color,
    location,
    date
):
    """
    Analyze a Lost/Found report and generate
    a simple AI-style explanation.
    """

    report_type = (report_type or "").strip().upper()
    title = (title or "").strip()
    description = (description or "").strip()
    category = (category or "").strip()
    color = (color or "").strip()
    location = (location or "").strip()
    date = (date or "").strip()

    # ----------------------------------------------------
    # Determine report type
    # ----------------------------------------------------

    if report_type == "LOST":
        report_label = "LOST"
        opposite_type = "FOUND"

    elif report_type == "FOUND":
        report_label = "FOUND"
        opposite_type = "LOST"

    else:
        report_label = "UNKNOWN"
        opposite_type = "LOST or FOUND"

    # ----------------------------------------------------
    # Determine item name
    # ----------------------------------------------------

    if title:
        item_name = title
    elif category:
        item_name = category
    else:
        item_name = "item"

    # ----------------------------------------------------
    # Build AI explanation
    # ----------------------------------------------------

    explanation = (
        f"This report is identified as a {report_label} item. "
        f"The item appears to be a {item_name}."
    )

    if color:
        explanation += (
            f" The reported color is {color}."
        )

    if location:
        explanation += (
            f" The reported location is {location}."
        )

    if date:
        explanation += (
            f" The reported date is {date}."
        )

    explanation += (
        f" The system will compare this report with "
        f"{opposite_type} reports using description, "
        f"category, color, location, date, and image similarity "
        f"to identify potential matches."
    )

    return {
        "report_type": report_label,
        "item_name": item_name,
        "opposite_type": opposite_type,
        "explanation": explanation
    }