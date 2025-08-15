import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime
import io
import os
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
# Fetch Reviews & Google Business Info
# -------------------------
def fetch_reviews(name, api_key=None, max_reviews=25):
    reviews_data = []
    place = {}

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
                        f"website,opening_hours,geometry,types,place_id&key={api_key}"
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

    if len(reviews_data) < max_reviews:
        try:
            remaining = max_reviews - len(reviews_data)
            query = requests.utils.quote(name + " reviews")
            r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            snippets = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:remaining]
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
# Scrape Website for About Info
# -------------------------
def scrape_about(website_url):
    if not website_url:
        return {}
    try:
        r = requests.get(website_url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else ""
        meta_desc = ""
        desc_tag = soup.find("meta", attrs={"name":"description"}) or soup.find("meta", attrs={"property":"og:description"})
        if desc_tag and desc_tag.get("content"):
            meta_desc = desc_tag["content"].strip()
        h1_text = soup.find("h1").get_text().strip() if soup.find("h1") else ""
        return {"title": title, "meta_description": meta_desc, "h1": h1_text, "url": website_url}
    except Exception:
        return {}

# -------------------------
# CMS Score Helper
# -------------------------
def calculate_cms_score(row):
    score = 0
    count = 0
    # Convert relevant CMS metrics to numeric 1-5 scale
    metrics_map = {
        "Hospital overall rating": lambda x: float(x) if x not in ["Not Available", None] else None,
        "Mortality national comparison": lambda x: {"Below":5,"Same":3,"Above":1}.get(x, None),
        "Safety of care national comparison": lambda x: {"Below":5,"Same":3,"Above":1}.get(x, None),
        "Readmission national comparison": lambda x: {"Below":5,"Same":3,"Above":1}.get(x, None),
        "Patient experience rating": lambda x: float(x) if x not in ["Not Available", None] else None
    }
    for col, fn in metrics_map.items():
        if col in row:
            val = fn(row[col])
            if val is not None:
                score += val
                count += 1
    return round(score/count,2) if count else None

# -------------------------
# Load CMS
# -------------------------
cms_df = load_cms()
if cms_df.empty:
    st.stop()

# -------------------------
# User Input
# -------------------------
hospital_name = st.text_input("Enter Hospital/Healthcare Organization Name:")
state = st.text_input("State (optional):")
city = st.text_input("City (optional):")
api_key = st.text_input("Google Places API Key (optional, for detailed reviews):", type="password")

if hospital_name:
    matched_row, col, msg = match_org(hospital_name, cms_df, state, city)
    st.info(msg)
    if matched_row is not None:
        cms_score = calculate_cms_score(matched_row)
        st.write("### CMS Profile")
        st.dataframe(matched_row.to_frame().T)
        st.write(f"**CMS Score:** {cms_score}")

        st.write("### Google News")
        news = fetch_news(hospital_name)
        if news:
            st.dataframe(pd.DataFrame(news))
        else:
            st.info("No recent news found.")

        st.write("### Reviews & Business Info")
        reviews, place_info = fetch_reviews(hospital_name, api_key=api_key)
        if reviews:
            st.dataframe(pd.DataFrame(reviews))
        else:
            st.info("No reviews found.")

        st.write("### Website Info")
        website_url = place_info.get("website") if place_info else None
        about_info = scrape_about(website_url)
        st.json(about_info)

        # -------------------------
        # Excel Download
        # -------------------------
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            matched_row.to_frame().T.to_excel(writer, sheet_name="CMS Profile", index=False)
            if reviews:
                pd.DataFrame(reviews).to_excel(writer, sheet_name="Reviews", index=False)
            if news:
                pd.DataFrame(news).to_excel(writer, sheet_name="News", index=False)
            if about_info:
                pd.DataFrame([about_info]).to_excel(writer, sheet_name="Website Info", index=False)
        output.seek(0)
        st.download_button("Download Full Profile Excel", data=output, file_name=f"{hospital_name}_profile.xlsx")
