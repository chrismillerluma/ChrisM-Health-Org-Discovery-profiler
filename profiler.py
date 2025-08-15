import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime
import io
import os
import json
import re
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Healthcare Profiler (CMS + Reviews + News)", layout="wide")
st.title("Healthcare Organization Discovery Profiler")

CMS_URL = (
    "https://data.cms.gov/provider-data/sites/default/files/resources/"
    "893c372430d9d71a1c52737d01239d47_1753409109/Hospital_General_Information.csv"
)

# -------------------------
# Load CMS Data
# -------------------------
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
    st.error("Cannot load CMS data.")
    return pd.DataFrame()

# -------------------------
# Normalize Names
# -------------------------
def normalize_name(name):
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    for word in ['hospital', 'medical center', 'center', 'clinic']:
        name = name.replace(word, '')
    return name.strip()

# -------------------------
# Google Pre-Validation
# -------------------------
def google_search_name(name, limit=3):
    query = requests.utils.quote(name)
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for g in soup.find_all('div', class_='tF2Cxc')[:limit]:
            title = g.find('h3').get_text() if g.find('h3') else ''
            link = g.find('a')['href'] if g.find('a') else ''
            snippet = g.find('span', class_='aCOpRe').get_text() if g.find('span', class_='aCOpRe') else ''
            results.append({"title": title, "link": link, "snippet": snippet})
        return results
    except Exception:
        return []

# -------------------------
# Match Organization
# -------------------------
def match_org(name, df, state=None, city=None):
    df_filtered = df.copy()
    if state:
        df_filtered = df_filtered[df_filtered['State'].str.upper() == state.upper()]
    if city:
        df_filtered = df_filtered[df_filtered['City'].str.upper() == city.upper()]
    if df_filtered.empty:
        return None, None, "No facilities found with specified state/city"

    name_cols = [c for c in df.columns if "name" in c.lower()]
    col = name_cols[0]
    choices = df_filtered[col].dropna().tolist()
    choices_norm = [normalize_name(c) for c in choices]
    name_norm = normalize_name(name)

    match = process.extractOne(name_norm, choices_norm, scorer=fuzz.WRatio, score_cutoff=90)
    if match:
        _, score, idx = match
        return df_filtered.iloc[idx], col, f"Matched '{choices[idx]}' (score {score})"
    
    # Fallback
    subs = df_filtered[df_filtered[col].str.contains(name, case=False, na=False)]
    if not subs.empty:
        return subs.iloc[0], col, f"Substring fallback: '{subs.iloc[0][col]}'"
    return None, col, "No match found"

# -------------------------
# Fetch News
# -------------------------
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

# -------------------------
# Fetch Reviews (simplified)
# -------------------------
def fetch_reviews(name, api_key=None):
	# Try Google Places API first if key provided
    reviews_data = []
    if api_key:
        try:
            url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={requests.utils.quote(name)}&key={api_key}"
            data = requests.get(url, timeout=10).json()
            for r in data.get("results", [])[:5]:
                reviews_data.append({
                    "name": r.get("name"),
                    "rating": r.get("rating"),
                    "user_ratings_total": r.get("user_ratings_total"),
                    "address": r.get("formatted_address")
                })
            return reviews_data
        except Exception:
            pass
    # Fallback scraping Google search snippets
    try:
        query = requests.utils.quote(name + " reviews")
        r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:5]
        for s in snippets:
            reviews_data.append({"snippet": s})
        return reviews_data
    except Exception:
        return []

# -------------------------
# Main App
# -------------------------
df_cms = load_cms()

org = st.text_input("Organization Name (e.g., UCSF Medical Center)")
gkey = st.text_input("Google Places API Key (optional)", type="password")
search_button = st.button("Search")

if org and search_button:
    with st.spinner("Validating via Google search..."):
        google_hits = google_search_name(org, limit=3)
        st.subheader("Top Google Search Hits")
        for hit in google_hits:
            st.markdown(f"- [{hit['title']}]({hit['link']}) — {hit['snippet']}")
		
		# Try extracting state/city from top hit snippets
        city, state = None, None
        for hit in google_hits:
            snippet = hit['snippet']
            match = re.search(r'\b([A-Za-z\s]+),\s([A-Z]{2})\b', snippet)
            if match:
                city, state = match.group(1), match.group(2)
                break

    with st.spinner("Matching organization..."):
        match, name_col, msg = match_org(org, df_cms, state=state, city=city)
        st.info(msg)

    if match is not None:
        st.subheader("Facility Info")
        st.json(match.to_dict())

        with st.spinner("Fetching Google News..."):
            news = fetch_news(match.get("Hospital Name") or match[name_col], limit=5)
        st.subheader("Recent News")
        for n in news:
            st.markdown(f"- [{n['title']}]({n['link']}) — {n['date']}")

        with st.spinner("Fetching Reviews..."):
            revs = fetch_reviews(org, gkey)

        st.subheader("Reviews Table")
if revs:
    df_revs = pd.DataFrame(revs)
    expected_cols = ["name", "rating", "user_ratings_total", "address", "snippet"]
    for col in expected_cols:
        if col not in df_revs.columns:
            df_revs[col] = None
    st.dataframe(df_revs[expected_cols])

    # Show top 5 best reviews
    if "rating" in df_revs.columns and df_revs["rating"].notna().any():
        st.subheader("Top 5 Best Reviews")
        df_best = df_revs.sort_values("rating", ascending=False).head(5)
        st.dataframe(df_best[expected_cols])

        st.subheader("Top 5 Worst Reviews")
        df_worst = df_revs.sort_values("rating", ascending=True).head(5)
        st.dataframe(df_worst[expected_cols])
else:
    st.info("No reviews found.")
        else:
            st.info("No reviews found.")

        profile = {
            "org_input": org,
            "matched_name": match.get("Hospital Name") or match.to_dict(),
            "news": news,
            "reviews": revs,
            "timestamp": datetime.utcnow().isoformat()
        }
        st.download_button("Download Profile", json.dumps(profile, indent=2),
                           f"{org.replace(' ','_')}_profile.json")
    else:
        st.error("No match could be found.")
