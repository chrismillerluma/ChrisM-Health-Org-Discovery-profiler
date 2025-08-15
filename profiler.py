import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from rapidfuzz import process, fuzz
from datetime import datetime
import io
import os
import json
from textblob import TextBlob

st.set_page_config(page_title="Healthcare Profiler (CMS + Reviews + News)", layout="wide")
st.title("Healthcare Organization Discovery Profiler")

CMS_URL = (
    "https://data.cms.gov/provider-data/sites/default/files/resources/"
    "893c372430d9d71a1c52737d01239d47_1753409109/Hospital_General_Information.csv"
)

# --- Load CMS Data ---
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
    st.error("Cannot load CMS data (web or local).")
    return pd.DataFrame()

df_cms = load_cms()

# --- Name Matching ---
def match_org(name, df):
    name_cols = [c for c in df.columns if "name" in c.lower()]
    if not name_cols:
        return None, None, "No name column in CMS data"
    col = name_cols[0]
    choices = df[col].dropna().tolist()
    match = process.extractOne(name, choices, scorer=fuzz.WRatio, score_cutoff=60)
    if match:
        _, score, idx = match
        return df.iloc[idx], col, f"Matched '{choices[idx]}' (score {score})"
    subs = df[df[col].str.contains(name, case=False, na=False)]
    if not subs.empty:
        return subs.iloc[0], col, f"Substring fallback: '{subs.iloc[0][col]}'"
    return None, col, "No match found"

# --- Fetch Google News ---
def fetch_news(name, limit=5):
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(name)}"
    try:
        r = requests.get(url, timeout=10)
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:limit]
        return [{"title": i.find("title").text, "link": i.find("link").text, "date": i.find("pubDate").text} for i in items]
    except Exception:
        return []

# --- Fetch Google Reviews ---
def fetch_reviews(name, api_key=None):
    reviews_summary = []
    try:
        if api_key:
            url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={requests.utils.quote(name)}&key={api_key}"
            data = requests.get(url, timeout=10).json()
            places = data.get("results", [])
            for p in places[:5]:
                rev = {
                    "name": p.get("name"),
                    "rating": p.get("rating"),
                    "user_ratings_total": p.get("user_ratings_total"),
                    "good_points": [],
                    "bad_points": []
                }
                # Fallback: could scrape details
                reviews_summary.append(rev)
        else:
            # Fallback scraping (simplified)
            query = requests.utils.quote(name + " reviews")
            r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            spans = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:10]
            for s in spans:
                blob = TextBlob(s)
                polarity = blob.sentiment.polarity
                reviews_summary.append({
                    "text": s,
                    "sentiment": polarity,
                    "good_points": [s] if polarity >= 0.1 else [],
                    "bad_points": [s] if polarity <= -0.1 else []
                })
    except Exception as e:
        print("Reviews fetch error:", e)
    return reviews_summary

# --- Fetch U.S. News Highlights ---
def fetch_usnews(name):
    highlights = {"good_points": [], "bad_points": []}
    try:
        search_name = name.replace(" ", "-").lower()
        url = f"https://health.usnews.com/best-hospitals/area/{search_name}"
        r = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        # Example: scrape top highlight sections
        sections = soup.find_all("div", class_="Highlight__HighlightContent-sc-1xytw0g-0")
        for sec in sections:
            txt = sec.get_text(strip=True)
            if "top" in txt.lower() or "best" in txt.lower():
                highlights["good_points"].append(txt)
            else:
                highlights["bad_points"].append(txt)
    except Exception:
        pass
    return highlights

# --- Fetch Medicare Highlights ---
def fetch_medicare(name, state=None, city=None):
    highlights = {"good_points": [], "bad_points": []}
    try:
        query_name = requests.utils.quote(name)
        url = f"https://www.medicare.gov/care-compare/details/hospital/?city={city or ''}&state={state or ''}&zipcode=&search={query_name}"
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        texts = [t.get_text(strip=True) for t in soup.find_all("p")]
        for t in texts[:10]:
            if "excellent" in t.lower() or "high" in t.lower():
                highlights["good_points"].append(t)
            elif "low" in t.lower() or "poor" in t.lower():
                highlights["bad_points"].append(t)
    except Exception as e:
        print("Medicare fetch error:", e)
    return highlights

# --- Streamlit UI ---
org = st.text_input("Organization Name (e.g., UCSF Medical Center)")
state = st.text_input("State (optional)")
city = st.text_input("City (optional)")
gkey = st.text_input("Google Places API Key (optional)", type="password")
search_button = st.button("Search")

# --- Only fetch when Search is pressed ---
if org and search_button:
    with st.spinner("Matching organization..."):
        match, name_col, msg = match_org(org, df_cms, )
        st.info(msg)
    
    if match is not None:
        st.subheader("Facility Info")
        st.json(match.to_dict())
        
        with st.spinner("Fetching Google News..."):
            news = fetch_news(match.get(name_col) or org, limit=5)
        st.subheader("Recent News")
        for n in news:
            st.markdown(f"- [{n['title']}]({n['link']}) — {n['date']}")
        
        with st.spinner("Fetching Google Reviews..."):
            reviews = fetch_reviews(org, gkey)
        st.subheader("Google Reviews Highlights")
        good_pts = []
        bad_pts = []
        for r in reviews:
            if "good_points" in r:
                good_pts.extend(r["good_points"])
            if "bad_points" in r:
                bad_pts.extend(r["bad_points"])
        st.markdown("**Good Points:**")
        st.write(good_pts[:5])
        st.markdown("**Bad Points:**")
        st.write(bad_pts[:5])
        
        with st.spinner("Fetching U.S. News Highlights..."):
            usnews = fetch_usnews(org)
        st.subheader("U.S. News Highlights")
        st.markdown("**Good Points:**")
        st.write(usnews["good_points"][:5])
        st.markdown("**Bad Points:**")
        st.write(usnews["bad_points"][:5])
        
        with st.spinner("Fetching Medicare Highlights..."):
            medicare = fetch_medicare(org, state=state, city=city)
        st.subheader("Medicare Highlights")
        st.markdown("**Good Points:**")
        st.write(medicare["good_points"][:5])
        st.markdown("**Bad Points:**")
        st.write(medicare["bad_points"][:5])
        
        profile = {
            "org_input": org,
            "matched_name": match.get(name_col) or match.to_dict(),
            "news": news,
            "reviews": reviews,
            "usnews": usnews,
            "medicare": medicare,
            "timestamp": datetime.utcnow().isoformat()
        }
        st.download_button("Download Profile", json.dumps(profile, indent=2), f"{org.replace(' ','_')}_profile.json")
    else:
        st.error("No match could be found.")
