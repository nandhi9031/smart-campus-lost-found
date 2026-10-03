import cv2


# ============================================================
# IMAGE SIMILARITY
# ============================================================

def calculate_image_similarity(image1_path, image2_path):

    # Read images
    image1 = cv2.imread(image1_path)
    image2 = cv2.imread(image2_path)

    # If image cannot be loaded
    if image1 is None or image2 is None:
        print("Could not load image:")
        print(image1_path)
        print(image2_path)
        return 0

    # Resize images
    image1 = cv2.resize(image1, (200, 200))
    image2 = cv2.resize(image2, (200, 200))

    # Convert BGR to HSV
    hsv1 = cv2.cvtColor(image1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(image2, cv2.COLOR_BGR2HSV)

    # Create histograms
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

    # Normalize
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)

    # Compare
    similarity = cv2.compareHist(
        hist1,
        hist2,
        cv2.HISTCMP_CORREL
    )

    # Convert to percentage
    score = ((similarity + 1) / 2) * 100

    score = max(0, min(100, score))

    return round(score, 2)