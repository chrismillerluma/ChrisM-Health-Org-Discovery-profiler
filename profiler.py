import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from rapidfuzz import process, fuzz
from datetime import datetime
import time
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
    # Try to load CMS from URL
    try:
        r = requests.get(CMS_URL, timeout=15)
        df = pd.read_csv(io.BytesIO(r.content), dtype=str, on_bad_lines="skip")
        st.success(f"Loaded CMS from web ({len(df)} records)")
        return df
    except Exception as e:
        st.warning(f"Failed loading CMS from URL: {e}")
    # Try local backup
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

def match_org(name, df):
    common_cols = [c for c in df.columns if "name" in c.lower()]
    if not common_cols:
        return None, "No name column in CMS data"
    col = common_cols[0]
    choices = df[col].dropna().tolist()
    match = process.extractOne(name, choices, scorer=fuzz.WRatio, score_cutoff=60)
    if match:
        _, score, idx = match
        return df.iloc[idx], f"Matched '{choices[idx]}' (score {score})"
    else:
        # substring search
        subs = df[df[col].str.contains(name, case=False, na=False)]
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
    if api_key:
        try:
            url = (
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
                f"?query={requests.utils.quote(name)}&key={api_key}"
            )
            data = requests.get(url, timeout=10).json()
            return data.get("results", [])
        except Exception:
            pass
    # fallback scraping
    try:
        query = requests.utils.quote(name + " reviews")
        r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        return [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:5]
    except Exception:
        return []

df_cms = load_cms()
org = st.text_input("Organization Name (e.g., UCSF Medical Center)")
gkey = st.text_input("Google Places API Key (optional)", type="password")

if org:
    with st.spinner("Matching organization..."):
        match, msg = match_org(org, df_cms)
        st.info(msg)
    if match is not None:
        st.subheader("Facility Info")
        st.json(match.to_dict())
        
        with st.spinner("Fetching Google News..."):
            news = fetch_news(match.get("Hospital Name") or match.get(match.index[0]), limit=5)
        st.subheader("Recent News")
        for n in news:
            st.markdown(f"- [{n['title']}]({n['link']}) — {n['date']}")
        
        with st.spinner("Fetching Reviews..."):
            revs = fetch_reviews(org, gkey)
        st.subheader("Google Reviews (or Fallback)")
        st.write(revs)
        
        profile = {
            "org_input": org,
            "matched_name": match.get("Hospital Name") or match.to_dict(),
            "news": news,
            "reviews": revs,
            "timestamp": datetime.utcnow().isoformat()
        }
        st.download_button("Download Profile", json.dumps(profile, indent=2), f"{org.replace(' ','_')}_profile.json")
    else:
        st.error("No match could be found.")

