import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
import re
from datetime import datetime

st.set_page_config(page_title="Healthcare Profiler", layout="wide")
st.title("Healthcare Organization Discovery Profiler")

# -------------------------
# Load CMS Spreadsheet
# -------------------------
@st.cache_data
def load_cms_data():
    try:
        # Replace with your actual spreadsheet path
        df = pd.read_csv("cms_data.csv")
        st.success(f"Loaded CMS data ({len(df)} records)")
        return df
    except Exception as e:
        st.error(f"Failed loading CMS data: {e}")
        return pd.DataFrame()

df_cms = load_cms_data()

# -------------------------
# Normalize Names
# -------------------------
def normalize_name(name):
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    for word in ['hospital', 'medical center', 'center', 'clinic']:
        name = name.replace(word, '')
    return name.strip()

# -------------------------
# Match Organization
# -------------------------
def match_org(name, df, state=None, city=None):
    df_filtered = df.copy()
    if state:
        df_filtered = df_filtered[df_filtered['state'].str.upper() == state.upper()]
    if city:
        df_filtered = df_filtered[df_filtered['city'].str.upper() == city.upper()]
    if df_filtered.empty:
        return None, None, "No facilities found with specified state/city"

    name_cols = [c for c in df.columns if "name" in c.lower()]
    col = name_cols[0]
    choices = df_filtered[col].dropna().tolist()
    choices_norm = [normalize_name(c) for c in choices]
    name_norm = normalize_name(name)

    match = process.extractOne(name_norm, choices_norm, scorer=fuzz.WRatio, score_cutoff=85)
    if match:
        _, score, idx = match
        return df_filtered.iloc[idx], col, f"Matched '{choices[idx]}' (score {score})"

    # fallback substring
    subs = df_filtered[df_filtered[col].str.contains(name, case=False, na=False)]
    if not subs.empty:
        return subs.iloc[0], col, f"Substring fallback: '{subs.iloc[0][col]}'"
    return None, col, "No match found"

# -------------------------
# Fetch Reviews
# -------------------------
def fetch_reviews(name):
    reviews_data = []
    try:
        query = requests.utils.quote(name + " reviews")
        r = requests.get(f"https://www.google.com/search?q={query}", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = [span.get_text() for span in soup.find_all("span") if len(span.get_text()) > 20][:20]
        for s in snippets:
            reviews_data.append({"snippet": s})
    except Exception:
        reviews_data.append({"snippet": "Failed to fetch reviews"})
    return reviews_data

# -------------------------
# Main App
# -------------------------
org = st.text_input("Organization Name (e.g., UCSF Medical Center)")
search_button = st.button("Search")

if org and search_button:
    with st.spinner("Matching organization..."):
        match, name_col, msg = match_org(org, df_cms)
        st.info(msg)

    if match is not None:
        st.subheader("Facility Info")
        st.json(match.to_dict())

        with st.spinner("Fetching Reviews..."):
            revs = fetch_reviews(org)
            st.subheader("Reviews")
            df_revs = pd.DataFrame(revs)
            # Top 5 / Worst 5 logic for snippets (if we had ratings we could sort)
            st.markdown("**Top Reviews:**")
            st.dataframe(df_revs.head(5))
            st.markdown("**Worst Reviews:**")
            st.dataframe(df_revs.tail(5))

        profile = {
            "org_input": org,
            "matched_name": match.get(name_col) or match.to_dict(),
            "cms_data": match.to_dict(),
            "reviews": revs,
            "timestamp": datetime.utcnow().isoformat()
        }
        st.download_button("Download Profile", pd.io.json.dumps(profile, indent=2),
                           f"{org.replace(' ','_')}_profile.json")
    else:
        st.error("No match could be found.")
