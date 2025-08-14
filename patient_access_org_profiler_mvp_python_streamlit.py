import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime
import time
import streamlit as st

# -----------------------------
# Logging / progress updates
# -----------------------------
def log(msg):
    st.write(msg)
    st.progress(0)  # dummy to trigger refresh

# -----------------------------
# Load local CMS backup
# -----------------------------
@st.cache_data
def load_cms_data(file_path='cms_local_backup.csv'):
    df = pd.read_csv(file_path)
    return df

# -----------------------------
# Name matching with fallback
# -----------------------------
def find_best_match(name, df, top_n=3):
    choices = df['Provider Name'].tolist()
    result = process.extract(name, choices, scorer=fuzz.token_sort_ratio, limit=top_n)
    good_matches = [r for r in result if r[1] >= 70]
    if good_matches:
        best_name, score, idx = good_matches[0]
        log(f"Local match found: {best_name} (score {score})")
        return df.iloc[idx]
    else:
        log("No strong local match, trying search fallback...")
        candidates = search_org_online(name)
        for candidate in candidates:
            r = process.extractOne(candidate, choices, scorer=fuzz.token_sort_ratio, score_cutoff=50)
            if r:
                match_name, score, idx = r
                log(f"Matched via search: {match_name} (score {score})")
                return df.iloc[idx]
        log("No match found")
        return None

# -----------------------------
# Online search for candidate org names
# -----------------------------
def search_org_online(name, max_results=5):
    query = "+".join(name.split())
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        candidates = [h.get_text().strip() for h in soup.find_all('h3')][:max_results]
        log(f"Found {len(candidates)} candidates online")
        time.sleep(1)
        return candidates
    except Exception as e:
        log(f"Search failed: {e}")
        return []

# -----------------------------
# Scrape reviews from websites
# -----------------------------
def scrape_reviews(org_name):
    reviews = []
    # Example: Google Reviews scraping (very simplified)
    query = "+".join(org_name.split()) + "+reviews"
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for div in soup.find_all('div'):
            text = div.get_text().strip()
            if len(text) > 30:
                reviews.append(text)
        log(f"Collected {len(reviews)} reviews")
    except Exception as e:
        log(f"Review scraping failed: {e}")
    return reviews

# -----------------------------
# Scrape news
# -----------------------------
def scrape_news(org_name):
    news = []
    query = "+".join(org_name.split()) + "+news"
    url = f"https://www.google.com/search?q={query}&tbm=nws"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for h3 in soup.find_all('h3'):
            news.append(h3.get_text().strip())
        log(f"Found {len(news)} news headlines")
    except Exception as e:
        log(f"News scraping failed: {e}")
    return news

# -----------------------------
# Main Streamlit app
# -----------------------------
st.title("Healthcare Organization Discovery Profiler")
df_cms = load_cms_data()

org_name_input = st.text_input("Enter Organization Name or Vendor:")

if org_name_input:
    st.info("Finding best match...")
    match_record = find_best_match(org_name_input, df_cms)
    if match_record is not None:
        st.success(f"Match found: {match_record['Provider Name']}")
        st.write(match_record)
        
        st.info("Gathering reviews...")
        reviews = scrape_reviews(match_record['Provider Name'])
        st.write(reviews[:10])  # show first 10
        
        st.info("Gathering news...")
        news = scrape_news(match_record['Provider Name'])
        st.write(news[:10])
    else:
        st.error("No match found in CMS or online search")
