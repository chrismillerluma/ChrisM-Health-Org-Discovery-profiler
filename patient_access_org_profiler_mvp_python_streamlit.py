import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime
import time

st.set_page_config(page_title="Healthcare Org Profiler", layout="wide")

st.title("Healthcare Organization Discovery Profiler")
org_name = st.text_input("Enter organization or vendor name (e.g., UCSF Medical Center)")

# Progress indicator
progress_text = st.empty()
progress_bar = st.progress(0)

def update_progress(step, total_steps, message=""):
    progress_bar.progress(step / total_steps)
    progress_text.text(message)

# Example function: fetch CMS hospital data locally (or you can extend to web)
@st.cache_data
def load_cms_data():
    try:
        df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
        return df
    except Exception as e:
        st.warning("CMS data could not be loaded. Using empty dataset.")
        return pd.DataFrame(columns=["Hospital Name", "City", "State", "Beds", "Ownership", "Rating"])

# Fuzzy matching
def find_best_match(name, choices):
    if not choices:
        return None, 0
    match, score, _ = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)
    return match, score

# Simple scraper for Google search results (news, reviews)
def fetch_google_results(query, max_results=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    search_url = f"https://www.google.com/search?q={query}&num={max_results}"
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for g in soup.find_all('div', class_='tF2Cxc')[:max_results]:
            title_tag = g.find('h3')
            link_tag = g.find('a')
            snippet_tag = g.find('div', class_='VwiC3b')
            if title_tag and link_tag and snippet_tag:
                results.append({
                    "title": title_tag.text,
                    "link": link_tag['href'],
                    "snippet": snippet_tag.text
                })
        return results
    except Exception as e:
        return []

# Scraper for Yelp (basic)
def fetch_yelp_reviews(name, location=""):
    try:
        query = f"{name} {location} site:yelp.com"
        return fetch_google_results(query, max_results=3)
    except:
        return []

# Scraper for RateMDs (basic)
def fetch_ratemd_reviews(name, location=""):
    try:
        query = f"{name} {location} site:ratemds.com"
        return fetch_google_results(query, max_results=3)
    except:
        return []

if org_name:
    total_steps = 5
    step = 0

    update_progress(step, total_steps, "Loading CMS data...")
    df_cms = load_cms_data()
    step += 1
    time.sleep(0.5)

    update_progress(step, total_steps, "Matching organization name...")
    org_match, match_score = find_best_match(org_name, df_cms["Hospital Name"].tolist())
    step += 1
    time.sleep(0.5)

    update_progress(step, total_steps, "Fetching news articles...")
    news_results = fetch_google_results(f"{org_name} news", max_results=5)
    step += 1
    time.sleep(0.5)

    update_progress(step, total_steps, "Fetching Yelp reviews...")
    yelp_results = fetch_yelp_reviews(org_name)
    step += 1
    time.sleep(0.5)

    update_progress(step, total_steps, "Fetching RateMDs reviews...")
    ratemd_results = fetch_ratemd_reviews(org_name)
    step += 1
    time.sleep(0.5)

    progress_text.text("Data retrieval complete!")
    progress_bar.empty()

    st.subheader(f"Organization Match: {org_match} (Score: {match_score})")
    if not df_cms.empty and org_match:
        org_data = df_cms[df_cms["Hospital Name"] == org_match].to_dict(orient="records")[0]
        st.write("### Organization Stats")
        st.json(org_data)

    st.write("### News Highlights")
    for news in news_results:
        st.markdown(f"- [{news['title']}]({news['link']}): {news['snippet']}")

    st.write("### Yelp Reviews (Sample)")
    for review in yelp_results:
        st.markdown(f"- [{review['title']}]({review['
