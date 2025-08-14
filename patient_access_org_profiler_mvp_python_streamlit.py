import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime
import json
import time

# -----------------------------
# Utility Functions
# -----------------------------

def fetch_cms_data(org_name):
    """
    Fetch CMS Hospital Compare data (local CSV backup as placeholder)
    """
    try:
        df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
        # Fuzzy match hospital name
        matches = process.extract(org_name, df['hospital_name'], scorer=fuzz.WRatio, limit=3)
        best_match_name, score, idx = matches[0]
        df_match = df[df['hospital_name'] == best_match_name]
        return df_match.to_dict(orient='records')[0] if not df_match.empty else {}
    except Exception as e:
        return {"error": f"Unable to load CMS data: {e}"}

def fetch_google_reviews(org_name):
    """
    Scrape Google reviews (simplified example, no API)
    """
    try:
        search_url = f"https://www.google.com/search?q={org_name.replace(' ', '+')}+reviews"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        reviews = [v.get_text() for v in soup.find_all("span") if "review" in v.get_text().lower()]
        return reviews[:10]  # top 10 reviews
    except:
        return []

def fetch_yelp_reviews(org_name, location="San Francisco, CA"):
    """
    Scrape Yelp reviews (simplified)
    """
    try:
        search_url = f"https://www.yelp.com/search?find_desc={org_name.replace(' ', '+')}&find_loc={location.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        reviews = [v.get_text() for v in soup.find_all("p")]
        return reviews[:10]
    except:
        return []

def fetch_ratemd_reviews(org_name, location="San Francisco, CA"):
    """
    Scrape RateMD reviews
    """
    try:
        search_url = f"https://www.ratemds.com/best-doctors/?s={org_name.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        reviews = [v.get_text() for v in soup.find_all("div", {"class": "review"})]
        return reviews[:10]
    except:
        return []

def fetch_news(org_name):
    """
    Scrape Google News
    """
    try:
        search_url = f"https://news.google.com/search?q={org_name.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        headlines = [v.get_text() for v in soup.find_all("a")]
        return headlines[:10]
    except:
        return []

def summarize_data(cms, google, yelp, ratemd, news):
    """
    Create highlights summary
    """
    summary = {
        "CMS Stats": cms,
        "Positive Highlights": [],
        "Negative Highlights": [],
        "Challenges / Notes": [],
        "Key Reviews": {
            "Google": google,
            "Yelp": yelp,
            "RateMD": ratemd,
        },
        "Recent News": news
    }
    
    # Simplified sentiment highlights (example)
    for r in google + yelp + ratemd:
        r_lower = r.lower()
        if any(w in r_lower for w in ["good", "excellent", "friendly", "helpful"]):
            summary["Positive Highlights"].append(r)
        elif any(w in r_lower for w in ["bad", "poor", "long wait", "rude"]):
            summary["Negative Highlights"].append(r)
        else:
            summary["Challenges / Notes"].append(r)
    return summary

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("Organization Review & Stats Profiler")

org_input = st.text_input("Enter Organization / Hospital / Vendor Name:", "UCSF Medical Center")
location_input = st.text_input("Location (City, State)", "San Francisco, CA")

if st.button("Generate Report"):
    st.info("Fetching data. This may take a minute...")
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    step = 0
    total_steps = 5
    
    progress_text.text("Fetching CMS data...")
    cms_data = fetch_cms_data(org_input)
    step += 1
    progress_bar.progress(step / total_steps)
    
    progress_text.text("Fetching Google reviews...")
    google_reviews = fetch_google_reviews(org_input)
    step += 1
    progress_bar.progress(step / total_steps)
    
    progress_text.text("Fetching Yelp reviews...")
    yelp_reviews = fetch_yelp_reviews(org_input, location_input)
    step += 1
    progress_bar.progress(step / total_steps)
    
    progress_text.text("Fetching RateMD reviews...")
    ratemd_reviews = fetch_ratemd_reviews(org_input, location_input)
    step += 1
    progress_bar.progress(step / total_steps)
    
    progress_text.text("Fetching news articles...")
    news_articles = fetch_news(org_input)
    step += 1
    progress_bar.progress(step / total_steps)
    
    progress_text.text("Generating summary...")
    report = summarize_data(cms_data, google_reviews, yelp_reviews, ratemd_reviews, news_articles)
    
    st.success("Report generated!")
    
    st.header("Highlights Summary")
    st.subheader("CMS Stats")
    st.json(report["CMS Stats"])
    
    st.subheader("Positive Highlights")
    st.write(report["Positive Highlights"])
    
    st.subheader("Negative Highlights")
    st.write(report["Negative Highlights"])
    
    st.subheader("Challenges / Notes")
    st.write(report["Challenges / Notes"])
    
    st.subheader("Key Reviews")
    st.write("Google Reviews:", report["Key Reviews"]["Google"])
    st.write("Yelp Reviews:", report["Key Reviews"]["Yelp"])
    st.write("RateMD Reviews:", report["Key Reviews"]["RateMD"])
    
    st.subheader("Recent News")
    st.write(report["Recent News"])
    
    st.subheader("Full JSON Dossier")
    st.json(report)
