from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# Load pretrained AI language model
model = SentenceTransformer('all-MiniLM-L6-v2')


def calculate_text_similarity(text1, text2):

    # Convert text into AI embeddings
    embedding1 = model.encode([text1])
    embedding2 = model.encode([text2])

    # Calculate cosine similarity
    similarity = cosine_similarity(
        embedding1,
        embedding2
    )[0][0]

    # Convert to percentage
    score = similarity * 100

    return round(score, 2)


if __name__ == '__main__':

    lost_description = (
        "gold bracelet 4 grams lost near PKIET xerox shop"
    )

    found_description = (
        "small gold bracelet weighing around 4 grams "
        "found near the PKIET xerox shop"
    )

    score = calculate_text_similarity(
        lost_description,
        found_description
    )

    print("Text Similarity:", score, "%")