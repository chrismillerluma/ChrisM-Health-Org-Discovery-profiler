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
                df_revs = df_revs.sort_values("rating", ascending=True)
            st.dataframe(df_revs[expected_cols].head(25))
        else:
            st.info("No reviews found.")

        st.subheader("Google Business Profile Info")
        if place_info:
            st.json({
                "name": place_info.get("name"),
                "address": place_info.get("formatted_address"),
                "rating": place_info.get("rating"),
                "user_ratings_total": place_info.get("user_ratings_total"),
                "phone": place_info.get("formatted_phone_number"),
                "international_phone": place_info.get("international_phone_number"),
                "website": place_info.get("website"),
                "opening_hours": place_info.get("opening_hours"),
                "geometry": place_info.get("geometry"),
                "types": place_info.get("types"),
                "place_id": place_info.get("place_id")
            })

        about_data = scrape_about(place_info.get("website") if place_info else None)
        if about_data:
            st.subheader("About Information (Scraped from Website)")
            st.json(about_data)

        with st.spinner("Calculating Business Performance / Reputation Score..."):
            try:
                if place_info:
                    rating = place_info.get("rating", 0)
                    total_reviews = place_info.get("user_ratings_total", 1)
                    rep_score = round(rating * min(total_reviews / 100, 1) * 20, 2)
                    st.subheader("Business Performance / Reputation Score")
                    st.markdown(f"- **Score (0-20)**: {rep_score}")
                    st.markdown(f"- **Rating**: {rating} / 5")
                    st.markdown(f"- **Total Reviews**: {total_reviews}")
                else:
                    st.info("Google Places API key required to calculate reputation score.")
            except Exception as e:
                st.warning(f"Could not calculate performance score: {e}")
        
        # -------------------------
        # Download Full Profile
        # -------------------------
        profile_data = {
            "org_input": org,
            "matched_name": match.get("Hospital Name") or match.to_dict(),
            "news": news,
            "reviews": revs,
            "business_profile": place_info,
            "about_info": about_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        st.subheader("Download Full Profile")
        # JSON
        json_bytes = json.dumps(profile_data, indent=2).encode('utf-8')
        st.download_button(
            label="Download Full Profile as JSON",
            data=json_bytes,
            file_name=f"{normalize_name(org)}_profile.json",
            mime="application/json"
        )
        # CSV (reviews only)
        if revs:
            df_revs_download = pd.DataFrame(revs)
            csv_bytes = df_revs_download.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Reviews as CSV",
                data=csv_bytes,
                file_name=f"{normalize_name(org)}_reviews.csv",
                mime="text/csv"
            )
