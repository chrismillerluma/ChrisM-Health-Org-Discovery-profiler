import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from rapidfuzz import process, fuzz
from datetime import datetime
from textblob import textBlob
import io
import os
import json

st.set_page_config(page_title="Healthcare Profiler (CMS + Reviews + News)", layout="wide")
st.title("Healthcare Organization Discovery Profiler")

CMS_URL = (
    "https://data.cms.gov/provider-data/sites/default/files/resources/"
    "893c372430d9d71a1c52737d01239d47_1753409109/Hospital_General_Information.csv"
)

@st.cache_data
def load_cms():
    try:
        r = requests.get(CMS_URL, timeout=15)
        df = pd.read_csv(io.BytesIO(r.content), dtype=str, on_bad_lines="skip")
        st.success(f"Loaded CMS from web ({len(df)} records)")
        return df
    except Exception as e:
        st.warning(f"Failed loading CMS from URL: {e}")
    if os.path.exists("cms_hospitals_backup.csv"):
        for enc in ["utf-8", "latin1", "utf-16"]:
            try:
                df = pd.read_csv("cms_hospitals_backup.csv", dtype=str, encoding=enc, on_bad_lines="skip")
                st.success(f"Loaded CMS from local backup ({enc})")
                return df
            except Exception:
                continue
    st.error("Cannot load CMS data (web or local). App cannot function.")
    return pd.DataFrame()

def match_org(name, df, state=None, city=None):
    common_cols = [c for c in df.columns if "name" in c.lower()]
    if not common_cols:
        return None, "No name column in CMS data"
    col = common_cols[0]
    df_filtered = df.copy()
    if state:
        df_filtered = df_filtered[df_filtered['State'].str.upper() == state.upper()]
    if city:
        df_filtered = df_filtered[df_filtered['City/Town'].str.upper() == city.upper()]
    if df_filtered.empty:
        return None, f"No facilities found with state={state} city={city}"
    choices = df_filtered[col].dropna().tolist()
    match = process.extractOne(name, choices, scorer=fuzz.WRatio, score_cutoff=60)
    if match:
        _, score, idx = match
        return df_filtered.iloc[idx], f"Matched '{choices[idx]}' (score {score})"
    # fallback substring
    subs = df_filtered[df_filtered[col].str.contains(name, case=False, na=False)]
    if not subs.empty:
        return subs.iloc[0], f"Substring fallback: '{subs.iloc[0][col]}'"
    return None, "No match found"

def fetch_news(name, limit=5):
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(name)}"
    try:
        r = requests.get(url, timeout=10)
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:limit]
        return [
            {"title": i.find("title").text, "link": i.find("link").text, "date": i.find("pubDate").text}
            for i in items
        ]
    except Exception:
        return []

def fetch_reviews(name, api_key=None):
    reviews = []
    if api_key:
        try:
            url = (
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
                f"?query={requests.utils.quote(name)}&key={api_key}"
            )
            data = requests.get(url, timeout=10).json()
            places = data.get("results", [])
            for p in places[:5]:
                reviews.append({
                    "text": f"{p.get('name')} (Rating: {p.get('rating')}, Reviews: {p.get('user_ratings_total')})"
                })
        except Exception:
            pass
    # fallback scraping Google search for reviews summary
    try:
        query = requests.utils.quote(name + " reviews")
        r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        spans = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20]
        for s in spans[:5]:
            reviews.append({"text": s})
    except Exception:
        pass
    return reviews

def fetch_usnews(name):
    highlights = []
    try:
        search_url = f"https://health.usnews.com/best-hospitals/search?utf8=✓&query={requests.utils.quote(name)}"
        r = requests.get(search_url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for div in soup.select("div.Block__BlockContent-sc-1bpgsv0-0"):
            text = div.get_text(strip=True)
            if text:
                highlights.append({"text": text})
        return highlights[:5]
    except Exception:
        return []

def fetch_medicare(rating_url):
    highlights = []
    try:
        r = requests.get(rating_url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("div.hospital-detail-card"):
            text = card.get_text(separator=" | ", strip=True)
            if text:
                highlights.append({"text": text})
        return highlights[:5]
    except Exception:
        return []

def classify_sentiment(items):
    good, bad = [], []
    for i in items:
        txt = i.get("text", "")
        if not txt:
            continue
        polarity = TextBlob(txt).sentiment.polarity
        if polarity > 0.1:
            good.append(txt)
        elif polarity < -0.1:
            bad.append(txt)
        else:
            good.append(txt)  # neutral treated as positive for highlights
    return good, bad

df_cms = load_cms()

st.subheader("Search for a Healthcare Organization")
org = st.text_input("Organization Name (e.g., UCSF Medical Center)")
state = st.text_input("State (optional, e.g., CA)")
city = st.text_input("City (optional, e.g., San Francisco)")
gkey = st.text_input("Google Places API Key (optional)", type="password")

search_button = st.button("Search")

# Name matching happens immediately for feedback
if org:
    match, msg = match_org(org, df_cms, state=state or None, city=city or None)
    st.info(msg)

if search_button and match is not None:
    st.subheader("Facility Info")
    st.json(match.to_dict())

    with st.spinner("Fetching Google News..."):
        news = fetch_news(match.get("Hospital Name") or match.to_dict().get(match.index[0], org))
    st.subheader("Recent News")
    for n in news:
        st.markdown(f"- [{n['title']}]({n['link']}) — {n['date']}")

    with st.spinner("Fetching Reviews..."):
        reviews = fetch_reviews(org, gkey)
    good_r, bad_r = classify_sentiment(reviews)
    st.subheader("Reviews Highlights")
    st.markdown("**Good Points:**")
    for r in good_r:
        st.markdown(f"- {r}")
    st.markdown("**Bad Points:**")
    for r in bad_r:
        st.markdown(f"- {r}")

    with st.spinner("Fetching US News Highlights..."):
        us_news = fetch_usnews(org)
    good_us, bad_us = classify_sentiment(us_news)
    st.subheader("US News Highlights")
    st.markdown("**Good Points:**")
    for h in good_us:
        st.markdown(f"- {h}")
    st.markdown("**Bad Points:**")
    for h in bad_us:
        st.markdown(f"- {h}")

    with st.spinner("Fetching Medicare Ratings/Highlights..."):
        medicare_url = f"https://www.medicare.gov/care-compare/details/hospital/{match.get('Facility ID')}/view-all"
        medicare_highlights = fetch_medicare(medicare_url)
    good_m, bad_m = classify_sentiment(medicare_highlights)
    st.subheader("Medicare Highlights")
    st.markdown("**Good Points:**")
    for h in good_m:
        st.markdown(f"- {h}")
    st.markdown("**Bad Points:**")
    for h in bad_m:
        st.markdown(f"- {h}")

    profile = {
        "org_input": org,
        "matched_name": match.get("Hospital Name") or match.to_dict(),
        "news": news,
        "reviews": reviews,
        "us_news": us_news,
        "medicare": medicare_highlights,
        "timestamp": datetime.utcnow().isoformat()
    }
    st.download_button("Download Profile", json.dumps(profile, indent=2), f"{org.replace(' ','_')}_profile.json")

elif search_button:
    st.error("No match could be found.")
