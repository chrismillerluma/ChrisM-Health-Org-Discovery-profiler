import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re

st.set_page_config(page_title="Healthcare Organization Discovery Profiler", layout="wide")
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
        return None, None, "No name column in CMS data"
    col = common_cols[0]
    df_filtered = df.copy()
    if state:
        df_filtered = df_filtered[df_filtered['State'].str.upper() == state.upper()]
    if city:
        df_filtered = df_filtered[df_filtered['City/Town'].str.upper() == city.upper()]
    if df_filtered.empty:
        return None, col, "No facilities found with specified state/city"
    choices = df_filtered[col].dropna().tolist()
    match = process.extractOne(name, choices, scorer=fuzz.WRatio, score_cutoff=85)
    if match:
        _, score, idx = match
        return df_filtered.iloc[idx], col, f"Matched '{choices[idx]}' (score {score})"
    subs = df_filtered[df_filtered[col].str.contains(name, case=False, na=False)]
    if not subs.empty:
        return subs.iloc[0], col, f"Substring fallback: '{subs.iloc[0][col]}'"
    return None, col, "No match found"

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
            search_url = (
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
                f"?query={requests.utils.quote(name)}&key={api_key}"
            )
            search_data = requests.get(search_url, timeout=10).json()
            results = search_data.get("results")
            if results:
                place_id = results[0]["place_id"]
                details_url = (
                    "https://maps.googleapis.com/maps/api/place/details/json"
                    f"?place_id={place_id}&fields=name,rating,reviews&key={api_key}"
                )
                details_data = requests.get(details_url, timeout=10).json()
                place_reviews = details_data.get("result", {}).get("reviews", [])
                if place_reviews:
                    sorted_reviews = sorted(place_reviews, key=lambda x: x.get("rating", 0), reverse=True)
                    top_good = sorted_reviews[:3]
                    top_bad = sorted_reviews[-3:]
                    reviews = {"good": top_good, "bad": top_bad}
                    return reviews
        except Exception as e:
            st.warning(f"Google Places API failed: {e}")
    try:
        query = requests.utils.quote(name + " reviews")
        r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:10]
        mid = len(snippets) // 2
        reviews = {"good": snippets[:mid], "bad": snippets[mid:]}
    except Exception as e:
        st.warning(f"Fallback review scraping failed: {e}")
    return reviews

def fetch_usnews_highlights(name):
    url = f"https://health.usnews.com/best-hospitals/area/ca/{requests.utils.quote(name)}"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        highlights = []
        for section in soup.find_all("section", class_="css-1h7qf4s"):
            title = section.find("h3")
            if title:
                highlights.append(title.get_text(strip=True))
        return highlights
    except Exception as e:
        st.warning(f"U.S. News highlights fetch failed: {e}")
    return []

def fetch_medicare_data(hospital_id):
    url = f"https://www.medicare.gov/care-compare/details/hospital/{hospital_id}/view-all"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        ratings = soup.find("div", class_="rating")
        if ratings:
            return ratings.get_text(strip=True)
    except Exception as e:
        st.warning(f"Medicare data fetch failed: {e}")
    return "No ratings available"

df_cms = load_cms()

org = st.text_input("Organization Name (e.g., UCSF Medical Center)")
state = st.text_input("State (optional, e.g., CA)").strip()
city = st.text_input("City (optional, e.g., San Francisco)").strip()
gkey = st.text_input("Google Places API Key (optional)", type="password")

search_button = st.button("Search")

if org:
    with st.spinner("Matching organization..."):
        match, name_col, msg = match_org(org, df_cms, state=state or None, city=city or None)
        st.info(msg)

    if match is not None and search_button:
        st.subheader("Facility Info")
        st.json(match.to_dict())

        with st.spinner("Fetching Google News..."):
            news = fetch_news(match.get(name_col), limit=5)
        st.subheader("Recent News")
        for n in news:
            st.markdown(f"- [{n['title']}]({n['link']}) — {n['date']}")

        with st.spinner("Fetching Reviews..."):
            revs = fetch_reviews(match.get(name_col), gkey)
        st.subheader("Top Reviews")
        st.markdown("**Positive:**")
        for r in revs.get("good", []):
            st.write(f"- {r.get('text', r) if isinstance(r, dict) else r} "
                     f"(Rating: {r.get('rating','N/A') if isinstance(r, dict) else 'N/A'})")

        st.markdown("**Negative:**")
        for r in revs.get("bad", []):
            st.write(f"- {r.get('text', r) if isinstance(r, dict) else r} "
                     f"(Rating: {r.get('rating','N/A') if isinstance(r, dict) else 'N/A'})")

        with st.spinner("Fetching U.S. News Highlights..."):
            usnews_highlights = fetch_usnews_highlights(match.get(name_col))
        st.subheader("U.S. News Highlights")
        if usnews_highlights:
            for highlight in usnews_highlights:
                st.write(f"- {highlight}")
        else:
            st.write("No highlights found.")

        with st.spinner("Fetching Medicare Ratings..."):
            medicare_ratings = fetch_medicare_data(match.get("Facility ID"))
        st.subheader("Medicare Ratings")
        st.write(medicare_ratings)

        profile = {
            "org_input": org,
            "matched_name": match.get(name_col) or match.to_dict(),
            "news": news,
            "reviews": revs,
            "usnews_highlights": usnews_highlights,
            "medicare_ratings": medicare_ratings,
            "timestamp": datetime.utcnow().isoformat()
        }
        st.download_button(
            "Download Profile",
            json.dumps(profile, indent=2),
            f"{org.replace(' ','_')}_profile.json"
        )
    else:
        st.error("No match could be found.")
