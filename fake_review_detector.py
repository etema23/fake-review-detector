"""
Fake review classifier.

Embeds product reviews with Cohere (embed-v4.0), trains a logistic regression
on the embeddings, and uses Command A+ to explain individual predictions.

Usage:
    export CO_API_KEY="..."
    python fake_review_detector.py

Dataset: https://www.kaggle.com/datasets/mexwell/fake-reviews-dataset
(saved as fake_reviews.csv)
"""

import time
import joblib
import numpy as np
import pandas as pd
import cohere
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

co = cohere.ClientV2()  # reads CO_API_KEY from the environment

EMBED_MODEL = "embed-v4.0"
CHAT_MODEL = "command-a-plus-05-2026"
BATCH_SIZE = 96  # Cohere's max texts per embed request
SAMPLE_SIZE = 2000  # subset of the 40k reviews to stay within trial-key limits


def embed(texts, sleep=0):
    """Embed a list of strings in batches. Returns an (n, dim) array."""
    vectors = []
    batches = range(0, len(texts), BATCH_SIZE)
    for n, i in enumerate(batches, start=1):
        batch = texts[i:i + BATCH_SIZE]
        while True:
            try:
                resp = co.embed(
                    model=EMBED_MODEL,
                    texts=batch,
                    input_type="classification",
                    embedding_types=["float"],
                )
                break
            except cohere.errors.TooManyRequestsError:
                # Trial keys are capped at 100k tokens/min, so back off and retry
                print("Rate limited, retrying in 60s...")
                time.sleep(60)
        vectors.extend(resp.embeddings.float_)
        if len(batches) > 1:
            print(f"Batch {n}/{len(batches)}")
        if sleep:
            time.sleep(sleep)
    return np.array(vectors)


def train(csv_path="fake_reviews.csv"):
    """Train the classifier, print evaluation metrics, and save it to model.joblib."""
    df = pd.read_csv(csv_path)
    df = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=42)
    df["is_fake"] = (df["label"] == "CG").astype(int)  # CG = computer-generated, OR = original

    X_train_txt, X_test_txt, y_train, y_test = train_test_split(
        df["text_"].tolist(), df["is_fake"].values,
        test_size=0.2, random_state=42, stratify=df["is_fake"],
    )

    # Cache embeddings so retraining doesn't re-embed (and re-spend API calls)
    try:
        saved = np.load("embeddings.npz")
        X_train, X_test = saved["X_train"], saved["X_test"]
        print("Loaded cached embeddings")
    except FileNotFoundError:
        print(f"Embedding {len(X_train_txt)} train + {len(X_test_txt)} test reviews")
        X_train = embed(X_train_txt, sleep=6)
        X_test = embed(X_test_txt, sleep=6)
        np.savez("embeddings.npz", X_train=X_train, X_test=X_test)

    clf = LogisticRegression(max_iter=2000)
    clf.fit(X_train, y_train)

    print(classification_report(y_test, clf.predict(X_test), target_names=["real", "fake"]))

    joblib.dump(clf, "model.joblib")
    return clf


def score(clf, reviews):
    """Return (review, probability of being fake) pairs."""
    probs = clf.predict_proba(embed(reviews))[:, 1]
    return list(zip(reviews, probs))


def explain(review, fake_prob):
    """Ask Command A+ which signals in the text support the classifier's verdict."""
    # Without the verdict in the prompt, the model tends to argue "fake" regardless of the score
    verdict = "likely fake" if fake_prob > 0.5 else "likely real"
    prompt = (
        f"A classifier rated this product review as {verdict} "
        f"({fake_prob:.0%} chance of being fake).\n\n"
        f'Review: "{review}"\n\n'
        "In 2-3 short bullet points, explain what in the text points toward that verdict. "
        "Signs of fake: vague praise, no product details, repetition, unnatural phrasing. "
        "Signs of real: specific details, dates, mixed opinions, natural or casual wording. "
        "If something goes against the verdict, mention it briefly. "
        "Don't invent facts about the reviewer."
    )
    resp = co.chat(model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}])
    # Command A+ returns a thinking block before the answer, so take the first text block
    for item in resp.message.content:
        if item.type == "text":
            return item.text
    return "No explanation returned."


if __name__ == "__main__":
    clf = train()

    # Sanity check on reviews outside the dataset (one real, one hype, one modern-AI style)
    test_reviews = [
        "Purchased on May 1st and by June 25th one on the cords no longer worked! This charger is usually used 1-2 times a week for our Ipad so not sure what the problem is. Doesn't work as lightening cables either. Not impressed.",
        "Absolutely amazing charger! This is easily the best charger I have ever purchased. It works perfectly every time and charges all of my devices incredibly fast. The quality is outstanding and I would recommend this product to everyone. Definitely worth every penny. Five stars!",
        "This charger provides a convenient solution for charging multiple devices. The cable length is practical for everyday use, and the charging performance is generally consistent. The materials feel reasonably durable, although long-term reliability may depend on usage. Overall, it is a functional charging accessory that should meet the needs of most users.",
    ]

    for text, p in score(clf, test_reviews):
        print("\n" + "-" * 50)
        print(f"{p:.0%} fake")
        print(text)
        if p > 0.5:
            print("\n" + explain(text, p))
