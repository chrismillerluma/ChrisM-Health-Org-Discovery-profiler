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

st.set_page_config(page_title="Healthcare Profiler (CMS + Reviews + News + Business Profile)", layout="wide")
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
# Fetch Reviews
# -------------------------
def fetch_reviews(name, api_key=None, max_reviews=25):
    reviews_data = []
    place = {}

    # 1️⃣ Google Places API
    if api_key:
        try:
            search_url = (
                f"https://maps.googleapis.com/maps/api/place/textsearch/json?"
                f"query={requests.utils.quote(name)}&key={api_key}"
            )
            search_resp = requests.get(search_url, timeout=10).json()
            results = search_resp.get("results", [])
            if results:
                place = results[0]
                place_id = place.get("place_id")
                if place_id:
                    details_url = (
                        f"https://maps.googleapis.com/maps/api/place/details/json?"
                        f"place_id={place_id}&fields=name,reviews,formatted_address,rating,"
                        f"user_ratings_total,formatted_phone_number,international_phone_number,"
                        f"website,opening_hours,geometry,types,photos&key={api_key}"
                    )
                    details_resp = requests.get(details_url, timeout=10).json()
                    place = details_resp.get("result", {})
                    for r in place.get("reviews", []):
                        reviews_data.append({
                            "name": place.get("name"),
                            "address": place.get("formatted_address"),
                            "rating": r.get("rating"),
                            "user_ratings_total": place.get("user_ratings_total"),
                            "author_name": r.get("author_name"),
                            "review_text": r.get("text"),
                            "time": datetime.utcfromtimestamp(r.get("time")).isoformat() if r.get("time") else None
                        })
        except Exception as e:
            st.warning(f"Failed to fetch reviews from API: {e}")

    # 2️⃣ Google Search Snippets fallback (improved)
    if len(reviews_data) < max_reviews:
        try:
            remaining = max_reviews - len(reviews_data)
            query = requests.utils.quote(name + " reviews")
            r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            
            review_spans = soup.find_all("span")
            snippets = []
            for span in review_spans:
                text = span.get_text()
                if len(text) > 30 and "review" in text.lower():
                    snippets.append(text)
                if len(snippets) >= remaining:
                    break
            
            for s in snippets:
                reviews_data.append({
                    "name": place.get("name") if place else None,
                    "address": place.get("formatted_address") if place else None,
                    "rating": None,
                    "user_ratings_total": place.get("user_ratings_total") if place else None,
                    "author_name": None,
                    "review_text": s,
                    "time": None
                })
        except Exception:
            pass

    return reviews_data[:max_reviews], place

# -------------------------
# Fetch About Info from Website
# -------------------------
def fetch_about_info(website):
    about_info = {}
    try:
        if website:
            if not website.startswith("http"):
                website = "https://" + website
            r = requests.get(website, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            about_info["meta_description"] = meta_desc["content"] if meta_desc else None
            
            # First 5 paragraphs
            paragraphs = soup.find_all("p")
            about_info["main_text"] = " ".join([p.get_text().strip() for p in paragraphs[:5]])
            
            # Try /about page
            about_page = requests.get(website.rstrip("/") + "/about", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            soup_about = BeautifulSoup(about_page.text, "html.parser")
            paragraphs_about = soup_about.find_all("p")
            if paragraphs_about:
                about_info["about_page_text"] = " ".join([p.get_text().strip() for p in paragraphs_about[:5]])
    except Exception as e:
        about_info["error"] = str(e)
    return about_info

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

        city, state = None, None
        for hit in google_hits:
            snippet = hit['snippet']
            match_loc = re.search(r'\b([A-Za-z\s]+),\s([A-Z]{2})\b', snippet)
            if match_loc:
                city, state = match_loc.group(1), match_loc.group(2)
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

        # -------------------------
        # Reviews & Business Profile
        # -------------------------
        with st.spinner("Fetching Reviews and Business Profile..."):
            revs, place_info = fetch_reviews(org, gkey, max_reviews=25)

        st.subheader("Reviews Table")
        if revs:
            df_revs = pd.DataFrame(revs)
            expected_cols = ["name", "author_name", "rating", "user_ratings_total", "address", "review_text", "time"]
            for col in expected_cols:
                if col not in df_revs.columns:
                    df_revs[col] = None
            if "rating" in df_revs.columns and df_revs["rating"].notna().any():
                df_revs = df_revs.sort_values(by="rating", ascending=False)
            st.dataframe(df_revs[expected_cols])
        else:
            st.info("No reviews found.")

        # -------------------------
        # About Section
        # -------------------------
        st.subheader("Organization About Info")
        if place_info.get("website"):
            about_data = fetch_about_info(place_info["website"])
            st.json(about_data)
        else:
            st.info("No website available to fetch About information.")
