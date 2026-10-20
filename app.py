"""
Streamlit version of the detector (built before the Chrome extension).

Usage:
    pip install streamlit
    streamlit run app.py

Requires model.joblib, so run fake_review_detector.py first.
"""

import joblib
import streamlit as st
from fake_review_detector import embed, explain

st.set_page_config(page_title="Fake Review Detector")


@st.cache_resource
def load_model():
    return joblib.load("model.joblib")


st.title("Fake Review Detector")
st.write("Paste a product review to check whether it's likely fake.")

review = st.text_area("Review", height=150)

if st.button("Check") and review.strip():
    clf = load_model()
    prob = clf.predict_proba(embed([review]))[0, 1]

    if prob > 0.5:
        st.error(f"Likely fake ({prob:.0%})")
    else:
        st.success(f"Likely real ({1 - prob:.0%})")
    st.progress(float(prob))

    with st.spinner("Getting explanation..."):
        st.markdown(explain(review, prob))
