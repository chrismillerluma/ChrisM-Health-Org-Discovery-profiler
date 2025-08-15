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
# Fetch Reviews with real text
# -------------------------
def fetch_reviews(name, api_key=None, max_reviews=25):
    reviews_data = []

    if api_key:
        try:
            search_url = (
                f"https://maps.googleapis.com/maps/api/place/textsearch/json?"
                f"query={requests.utils.quote(name)}&key={api_key}"
            )
            search_resp = requests.get(search_url, timeout=10).json()
            results = search_resp.get("results", [])
            if results:
                place_id = results[0].get("place_id")
                if place_id:
                    details_url = (
                        f"https://maps.googleapis.com/maps/api/place/details/json?"
                        f"place_id={place_id}&fields=name,reviews,formatted_address,rating,user_ratings_total"
                        f"&key={api_key}"
                    )
                    details_resp = requests.get(details_url, timeout=10).json()
                    place = details_resp.get("result", {})
                    # Google returns max 5 reviews per request; we can batch 5 times if needed
                    reviews = place.get("reviews", [])
                    for r in reviews[:max_reviews]:
                        reviews_data.append({
                            "name": place.get("name"),
                            "address": place.get("formatted_address"),
                            "rating": r.get("rating"),
                            "user_ratings_total": place.get("user_ratings_total"),
                            "author_name": r.get("author_name"),
                            "review_text": r.get("text"),
                            "time": datetime.utcfromtimestamp(r.get("time")).isoformat() if r.get("time") else None
                        })
            return reviews_data
        except Exception as e:
            st.warning(f"Failed to fetch reviews from API: {e}")

    # fallback scraping Google search snippets
    try:
        query = requests.utils.quote(name + " reviews")
        r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:max_reviews]
        for s in snippets:
            reviews_data.append({"review_text": s})
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
        # Reviews Section
        # -------------------------
        with st.spinner("Fetching Reviews..."):
            revs = fetch_reviews(org, gkey, max_reviews=25)

        st.subheader("Reviews Table")
        if revs:
            df_revs = pd.DataFrame(revs)
            expected_cols = ["name", "author_name", "rating", "user_ratings_total", "address", "review_text", "time"]
            for col in expected_cols:
                if col not in df_revs.columns:
                    df_revs[col] = None

            # Sort by lowest rating first if ratings exist
            if "rating" in df_revs.columns and df_revs["rating"].notna().any():
                df_revs = df_revs.sort_values("rating", ascending=True)
            
            st.dataframe(df_revs[expected_cols].head(25))
        else:
            st.info("No reviews found.")

        # -------------------------
        # Public Business Profile Section
        # -------------------------
        with st.spinner("Fetching Public Business Profile..."):
            if gkey:
                try:
                    profile_url = (
                        f"https://maps.googleapis.com/maps/api/place/textsearch/json?"
                        f"query={requests.utils.quote(org)}&key={gkey}"
                    )
                    profile_resp = requests.get(profile_url, timeout=10).json()
                    profile_results = profile_resp.get("results", [])
                    if profile_results:
                        place = profile_results[0]
                        st.subheader("Google Business Profile Info")
                        st.json({
                            "name": place.get("name"),
                            "address": place.get("formatted_address"),
                            "rating": place.get("rating"),
                            "user_ratings_total": place.get("user_ratings_total"),
                            "types": place.get("types"),
                            "place_id": place.get("place_id")
                        })

                        st.subheader("Top 25 Public Reviews")
                        public_reviews = fetch_reviews(org, gkey, max_reviews=25)
                        if public_reviews:
                            df_public_reviews = pd.DataFrame(public_reviews)
                            st.dataframe(df_public_reviews)
                except Exception as e:
                    st.warning(f"Could not fetch Google Business Profile info: {e}")
            else:
                st.info("Provide Google Places API key to fetch business profile info.")

# -------------------------
# Business Performance / Reputation Score
# -------------------------
with st.spinner("Calculating Business Performance / Reputation Score..."):
    try:
        if gkey:
            # Simple example: score = average rating / total reviews normalized
            rating = place.get("rating", 0)
            total_reviews = place.get("user_ratings_total", 1)
            rep_score = round(rating * min(total_reviews / 100, 1) * 20, 2)  # Scale 0-20
            st.subheader("Business Performance / Reputation Score")
            st.markdown(f"- **Score (0-20)**: {rep_score}")
            st.markdown(f"- **Rating**: {rating} / 5")
            st.markdown(f"- **Total Reviews**: {total_reviews}")
        else:
            st.info("Provide Google Places API key to calculate reputation score.")
    except Exception as e:
        st.warning(f"Could not calculate performance score: {e}")
        
        # -------------------------
        # Download Profile
        # -------------------------
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
