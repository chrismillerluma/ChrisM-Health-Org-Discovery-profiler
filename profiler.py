import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime
import io
import os
import json

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

# --- Fetch Google Reviews ---
def fetch_reviews(name, api_key=None):
    reviews_summary = {
        "average_rating": None,
        "total_reviews": None,
        "good_points": [],
        "bad_points": [],
        "top_reviews": []
    }
    try:
        if api_key:
            url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={requests.utils.quote(name)}&key={api_key}"
            data = requests.get(url, timeout=10).json()
            places = data.get("results", [])
            for p in places[:5]:
                place_id = p.get("place_id")
                details_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=rating,user_ratings_total,reviews&key={api_key}"
                details = requests.get(details_url, timeout=10).json()
                result = details.get("result", {})
                reviews_summary["average_rating"] = result.get("rating")
                reviews_summary["total_reviews"] = result.get("user_ratings_total")
                reviews = result.get("reviews", [])
                for review in reviews:
                    text = review.get("text", "")
                    rating = review.get("rating", 0)
                    if rating >= 4:
                        reviews_summary["good_points"].append(text)
                    elif rating <= 2:
                        reviews_summary["bad_points"].append(text)
                    reviews_summary["top_reviews"].append({
                        "author_name": review.get("author_name"),
                        "rating": rating,
                        "text": text
                    })
        else:
            # Fallback scraping (simplified)
            query = requests.utils.quote(name + " reviews")
            r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            spans = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:10]
            for s in spans:
                reviews_summary["top_reviews"].append({
                    "author_name": "Anonymous",
                    "rating": None,
                    "text": s
                })
    except Exception as e:
        print("Reviews fetch error:", e)
    return reviews_summary

# --- Streamlit UI ---
org = st.text_input("Organization Name (e.g., UCSF Medical Center)")
state = st.text_input("State (optional)")
city = st.text_input("City (optional)")
gkey = st.text_input("Google Places API Key (optional)", type="password")
search_button = st.button("Search")

# --- Only fetch when Search is pressed ---
if org and search_button:
    with st.spinner("Matching organization..."):
        match, name_col, msg = match_org(org, df_cms)
        st.info(msg)
    
    if match is not None:
        st.subheader("Facility Info")
        st.json(match.to_dict())
        
        with st.spinner("Fetching Google Reviews..."):
            reviews = fetch_reviews(org, gkey)
        st.subheader("Google Reviews Highlights")
        st.write(f"**Average Rating:** {reviews['average_rating']}")
        st.write(f"**Total Reviews:** {reviews['total_reviews']}")
        st.markdown("**Good Points:**")
        st.write(reviews["good_points"][:5])
        st.markdown("**Bad Points:**")
        st.write(reviews["bad_points"][:5])
        st.markdown("**Top Reviews:**")
        for review in reviews["top_reviews"][:5]:
            st.write(f"**{review['author_name']}**: {review['rating']} stars")
            st.write(f"  {review['text']}")
        
        profile = {
            "org_input": org,
            "matched_name": match.get(name_col) or match.to_dict(),
            "reviews": reviews,
            "timestamp": datetime.utcnow().isoformat()
        }
        st.download_button("Download Profile", json.dumps(profile, indent=2), f"{org.replace(' ','_')}_profile.json")
    else:
        st.error("No match could be found.")
