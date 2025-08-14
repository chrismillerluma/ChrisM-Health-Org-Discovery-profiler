import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
import json
from datetime import datetime
import time

# ------------------------------
# Helper functions
# ------------------------------

def log_progress(logs, message):
    logs.text(message)
    time.sleep(0.5)

def fetch_google_reviews(org_name, logs):
    log_progress(logs, f"Fetching Google reviews for {org_name}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    query = org_name.replace(" ", "+")
    url = f"https://www.google.com/search?q={query}+reviews"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    reviews = []

    for div in soup.find_all("div"):
        text = div.get_text().strip()
        if len(text) > 50 and "review" in text.lower():
            reviews.append(text)
        if len(reviews) >= 5:  # limit for speed
            break
    return reviews or ["No Google reviews found."]

def fetch_yelp_reviews(org_name, logs):
    log_progress(logs, f"Fetching Yelp reviews for {org_name}...")
    query = org_name.replace(" ", "-")
    url = f"https://www.yelp.com/search?find_desc={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    reviews = []

    for review in soup.find_all("p"):
        text = review.get_text().strip()
        if len(text) > 50:
            reviews.append(text)
        if len(reviews) >= 5:
            break
    return reviews or ["No Yelp reviews found."]

def fetch_news(org_name, logs):
    log_progress(logs, f"Fetching recent news for {org_name}...")
    query = org_name.replace(" ", "+")
    url = f"https://news.google.com/search?q={query}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    articles = []
    for a in soup.find_all("a"):
        title = a.get_text().strip()
        if len(title) > 20:
            articles.append(title)
        if len(articles) >= 5:
            break
    return articles or ["No news found."]

def summarize_reviews(reviews):
    positive = [r for r in reviews if "good" in r.lower() or "excellent" in r.lower()]
    negative = [r for r in reviews if "bad" in r.lower() or "poor" in r.lower()]
    return positive, negative

# ------------------------------
# Streamlit App
# ------------------------------

st.set_page_config(page_title="Org Discovery Profiler", layout="wide")
st.title("Organization / Vendor Discovery Profiler")

org_name = st.text_input("Enter organization or vendor name:", "")

if org_name:
    logs = st.empty()
    log_progress(logs, "Starting data collection...")

    # Google reviews
    google_reviews = fetch_google_reviews(org_name, logs)

    # Yelp reviews
    yelp_reviews = fetch_yelp_reviews(org_name, logs)

    # News articles
    news_articles = fetch_news(org_name, logs)

    # Combine reviews
    all_reviews = google_reviews + yelp_reviews
    positive, negative = summarize_reviews(all_reviews)

    # Display summary
    st.subheader("Summary Report")
    st.markdown(f"**Organization:** {org_name}")
    st.markdown(f"**Generated At:** {datetime.utcnow().isoformat()}")

    st.subheader("Highlights")
    st.markdown("**Positive Reviews:**")
    for r in positive:
        st.markdown(f"- {r}")

    st.markdown("**Negative Reviews / Challenges:**")
    for r in negative:
        st.markdown(f"- {r}")

    st.subheader("News & Mentions")
    for n in news_articles:
        st.markdown(f"- {n}")

    st.subheader("All Reviews Collected")
    for r in all_reviews:
        st.markdown(f"- {r}")

    log_progress(logs, "Data collection completed!")

