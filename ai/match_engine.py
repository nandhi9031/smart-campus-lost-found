import os
from datetime import datetime

from ai.text_matching import calculate_text_similarity
from ai.image_matching import calculate_image_similarity


# ============================================================
# CATEGORY MATCH
# ============================================================

def category_score(category1, category2):

    if not category1 or not category2:
        return 0

    if category1.lower() == category2.lower():
        return 100

    return 0


# ============================================================
# COLOR MATCH
# ============================================================

def color_score(color1, color2):

    if not color1 or not color2:
        return 0

    if color1.lower().strip() == color2.lower().strip():
        return 100

    return 0


# ============================================================
# LOCATION MATCH
# ============================================================

def location_score(location1, location2):

    if not location1 or not location2:
        return 0

    location1 = location1.lower().strip()
    location2 = location2.lower().strip()

    words1 = set(location1.split())
    words2 = set(location2.split())

    common_words = words1.intersection(words2)

    if location1 == location2:
        return 100

    if len(common_words) >= 2:
        return 100

    if len(common_words) == 1:
        return 50

    return 0


# ============================================================
# DATE MATCH
# ============================================================

def date_score(date1, date2):

    if not date1 or not date2:
        return 0

    try:

        d1 = datetime.strptime(date1, "%Y-%m-%d")
        d2 = datetime.strptime(date2, "%Y-%m-%d")

        difference = abs((d1 - d2).days)

        if difference == 0:
            return 100

        elif difference == 1:
            return 80

        elif difference == 2:
            return 60

        elif difference <= 5:
            return 30

        else:
            return 0

    except ValueError:

        return 0


# ============================================================
# FINAL MATCH CALCULATION
# ============================================================

def calculate_match(lost, found):

    # --------------------------------------------------------
    # TEXT MATCHING
    # --------------------------------------------------------

    lost_text = (
        f"{lost.title}. "
        f"{lost.description}. "
        f"{lost.category}. "
        f"{lost.color}. "
        f"{lost.location}"
    )

    found_text = (
        f"{found.title}. "
        f"{found.description}. "
        f"{found.category}. "
        f"{found.color}. "
        f"{found.location}"
    )

    text = calculate_text_similarity(
        lost_text,
        found_text
    )


    # --------------------------------------------------------
    # IMAGE MATCHING
    # --------------------------------------------------------

    image = 0

    if lost.image and found.image:

        base_folder = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        lost_image_path = os.path.join(
            base_folder,
            "static",
            "uploads",
            lost.image
        )

        found_image_path = os.path.join(
            base_folder,
            "static",
            "uploads",
            found.image
        )

        image = calculate_image_similarity(
            lost_image_path,
            found_image_path
        )


    # --------------------------------------------------------
    # OTHER MATCHING FACTORS
    # --------------------------------------------------------

    category = category_score(
        lost.category,
        found.category
    )

    color = color_score(
        lost.color,
        found.color
    )

    location = location_score(
        lost.location,
        found.location
    )

    date = date_score(
        lost.date,
        found.date
    )


    # ========================================================
    # FINAL WEIGHTED SCORE
    # ========================================================

    if lost.image and found.image:

        # ----------------------------------------------------
        # IMAGE AVAILABLE
        # ----------------------------------------------------
        # Text     = 35%
        # Image    = 30%
        # Category = 5%
        # Color    = 5%
        # Location = 15%
        # Date     = 10%
        # Total    = 100%
        # ----------------------------------------------------

        final_score = (
            (text * 0.35) +
            (image * 0.30) +
            (category * 0.05) +
            (color * 0.05) +
            (location * 0.15) +
            (date * 0.10)
        )

    else:

        # ----------------------------------------------------
        # IMAGE NOT AVAILABLE
        # ----------------------------------------------------
        # Redistribute image weight.
        #
        # Text     = 55%
        # Category = 15%
        # Color    = 10%
        # Location = 10%
        # Date     = 10%
        # Total    = 100%
        # ----------------------------------------------------

        final_score = (
            (text * 0.55) +
            (category * 0.15) +
            (color * 0.10) +
            (location * 0.10) +
            (date * 0.10)
        )


    final_score = round(final_score, 2)


    # ========================================================
    # MATCH LEVEL
    # ========================================================

    if final_score >= 90:

        level = "Very High Match"

    elif final_score >= 75:

        level = "High Match"

    elif final_score >= 60:

        level = "Possible Match"

    else:

        level = "Low Similarity"


    # ========================================================
    # RETURN MATCH RESULT
    # ========================================================

    return {

        "text": round(text, 2),

        "image": round(image, 2),

        "category": category,

        "color": color,

        "location": location,

        "date": date,

        "final_score": final_score,

        "level": level

    }