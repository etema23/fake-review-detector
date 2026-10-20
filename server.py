"""
Local API for the Chrome extension.

The extension sends review text here instead of calling Cohere directly, so the
API key stays on this machine rather than being bundled into the extension.

Usage:
    uvicorn server:app --port 8000
"""

from typing import List

import joblib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fake_review_detector import embed, explain

MAX_REVIEWS = 96  # one embed request per page
MAX_CHARS = 2000  # truncate unusually long reviews

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

clf = joblib.load("model.joblib")


class ScoreRequest(BaseModel):
    reviews: List[str]


class ExplainRequest(BaseModel):
    review: str
    prob: float


def clean(text):
    # Collapse whitespace so text copied into the popup and text read from the page
    # produce identical embeddings (copy-paste changes line breaks and spacing)
    return " ".join(text.split())[:MAX_CHARS]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score")
def score(req: ScoreRequest):
    texts = [clean(r) or "(empty)" for r in req.reviews[:MAX_REVIEWS]]
    if not texts:
        return {"probs": []}
    probs = clf.predict_proba(embed(texts))[:, 1].tolist()
    return {"probs": probs}


@app.post("/explain")
def explain_review(req: ExplainRequest):
    return {"explanation": explain(clean(req.review), req.prob)}
