import cv2
import numpy as np
import requests


def load_image(image_source):

    if not image_source:
        return None

    try:

        # Cloudinary / web image
        if image_source.startswith(
            ("http://", "https://")
        ):

            response = requests.get(
                image_source,
                timeout=10
            )

            response.raise_for_status()

            image_array = np.frombuffer(
                response.content,
                dtype=np.uint8
            )

            return cv2.imdecode(
                image_array,
                cv2.IMREAD_COLOR
            )

        # Local image
        return cv2.imread(
            image_source
        )

    except Exception as e:

        print(
            "Could not load image:",
            e
        )

        return None


def calculate_image_similarity(
    image1_source,
    image2_source
):

    image1 = load_image(
        image1_source
    )

    image2 = load_image(
        image2_source
    )

    if image1 is None or image2 is None:

        return 0

    # Resize images
    image1 = cv2.resize(
        image1,
        (200, 200)
    )

    image2 = cv2.resize(
        image2,
        (200, 200)
    )

    # Convert BGR to HSV
    hsv1 = cv2.cvtColor(
        image1,
        cv2.COLOR_BGR2HSV
    )

    hsv2 = cv2.cvtColor(
        image2,
        cv2.COLOR_BGR2HSV
    )

    # Create HSV histograms
    hist1 = cv2.calcHist(
        [hsv1],
        [0, 1],
        None,
        [50, 60],
        [0, 180, 0, 256]
    )

    hist2 = cv2.calcHist(
        [hsv2],
        [0, 1],
        None,
        [50, 60],
        [0, 180, 0, 256]
    )

    # Normalize histograms
    cv2.normalize(
        hist1,
        hist1
    )

    cv2.normalize(
        hist2,
        hist2
    )

    # Compare histograms
    similarity = cv2.compareHist(
        hist1,
        hist2,
        cv2.HISTCMP_CORREL
    )

    # Convert similarity to percentage
    score = (
        (similarity + 1) / 2
    ) * 100

    # Keep score between 0 and 100
    score = max(
        0,
        min(100, score)
    )

    return round(
        score,
        2
    )