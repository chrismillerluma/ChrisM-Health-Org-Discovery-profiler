# ChrisM-Health-Org-Discovery-profiler
A one-file app that takes a health system / hospital name and builds a pre-discovery customer profile

"""
Patient Access Org Profiler — MVP
---------------------------------
A one-file Streamlit app that takes a health system / hospital name and builds a
pre-discovery customer profile for Patient Access / Epic environments by pulling:
- Google Places (facility) basics + recent review themes
- CMS Care Compare open data (beds, type, address, quality signals)
- Web news/press releases (via Bing or Google Custom Search) — stubbed adapter
- KLAS summary placeholder (manual or private subscription input)
- LinkedIn company page basics — stubbed adapter

IMPORTANT
- Populate environment variables before running (see CONFIG section).
- Some sources require API keys and/or paid access; stubs provided with TODOs.
- Respect each site's Terms of Service and robots.txt when scraping.

Run:
  pip install streamlit pydantic requests python-dateutil nltk scikit-learn tldextract
  streamlit run app.py
"""
from __future__ import annotations
import os
import re
import json
import time
import textwrap
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

import requests
from dateutil import parser as dateparser

import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

import streamlit as st

# --------------- CONFIG ---------------
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")  # Required for Google reviews
BING_SEARCH_API_KEY   = os.getenv("BING_SEARCH_API_KEY")    # Optional for news/search
CMS_BASE = "https://data.cms.gov/data-api/v1/dataset"       # CMS Care Compare/other datasets

# --------------- UTILITIES ---------------
@st.cache_data(show_spinner=False)
def _http_get(url: str, params: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None):
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json() if "application/json" in r.headers.get("content-type", "") else r.text


def _safe(obj: Any) -> Any:
    try:
        return json.loads(json.dumps(obj))
    except Exception:
        return obj


# --------------- DATA SHAPES ---------------
@dataclass
class OrgProfile:
    query: str
    resolved_name: Optional[str] = None
    domains: List[str] = None
    basics: Dict[str, Any] = None
    cms: Dict[str, Any] = None
    google: Dict[str, Any] = None
    klas: Dict[str, Any] = None
    linkedin: Dict[str, Any] = None
    news: List[Dict[str, Any]] = None
    metrics: Dict[str, Any] = None
    risks: List[str] = None
    opportunities: List[str] = None
    generated_at: str = datetime.utcnow().isoformat()

    def to_json(self) -> str:
        return json.dumps(_safe(asdict(self)), indent=2)


# --------------- SOURCE ADAPTERS ---------------
@st.cache_data(show_spinner=False)
def google_places_find_facility(org_name: str, city_or_state_hint: str | None = None) -> Dict[str, Any]:
    """Find a place and fetch details + recent reviews via Places API.
    Requires GOOGLE_PLACES_API_KEY. Returns empty dict if missing.
    """
    if not GOOGLE_PLACES_API_KEY:
        return {}
    q = org_name if not city_or_state_hint else f"{org_name} {city_or_state_hint}"
    search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": q, "key": GOOGLE_PLACES_API_KEY}
    resp = _http_get(search_url, params)
    if not resp or resp.get("status") not in ("OK", "ZERO_RESULTS"):
        return {}
    results = resp.get("results", [])
    if not results:
        return {}
    place = results[0]
    place_id = place.get("place_id")
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    fields = [
        "name","formatted_address","formatted_phone_number","website","url","rating",
        "user_ratings_total","types","geometry/location","opening_hours","reviews"
    ]
    dparams = {"place_id": place_id, "fields": ",".join(fields), "key": GOOGLE_PLACES_API_KEY}
    details = _http_get(details_url, dparams)
    if details.get("status") != "OK":
        return {"summary": place}
    return details.get("result", {})


def _extract_review_themes(reviews: List[Dict[str, Any]] | None, k: int = 5) -> List[str]:
    if not reviews:
        return []
    texts = [r.get("text", "") for r in reviews if r.get("text")]
    if not texts:
        return []
    try:
        # lightweight TF-IDF + KMeans to surface themes
        vectorizer = TfidfVectorizer(stop_words="english", max_features=2000)
        X = vectorizer.fit_transform(texts)
        k = min(k, max(1, len(texts)))
        model = KMeans(n_clusters=k, n_init=5, random_state=42)
        model.fit(X)
        labels = model.labels_
        themes = []
        for cl in range(k):
            idx = [i for i, l in enumerate(labels) if l == cl]
            cluster_text = " ".join(texts[i] for i in idx)
            # take top terms per cluster
            sums = X[idx].sum(axis=0)
            terms = vectorizer.get_feature_names_out()
            top_idx = sums.A1.argsort()[-6:][::-1]
            themes.append(
                ", ".join(terms[i] for i in top_idx)
            )
        return themes
    except Exception:
        # Fallback: most frequent words
        words = re.findall(r"[A-Za-z]{4,}", " ".join(texts).lower())
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        return [w for w,_ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]]


@st.cache_data(show_spinner=False)
def cms_hospital_general_info(name_query: str) -> Dict[str, Any]:
    """Query CMS Care Compare: Hospital General Information (dataset id fixed).
    Returns the best fuzzy match record.
    """
    # Dataset: Hospital General Information — dataset-id: 77hc-ibv8 (as of 2025)
    dataset_id = "77hc-ibv8"
    url = f"{CMS_BASE}/{dataset_id}/data"
    # Simple name contains filter; client may refine
    params = {"search": name_query, "size": 50}
    try:
        data = _http_get(url, params)
        if not isinstance(data, list) or not data:
            return {}
        # pick record with highest overlap score
        def score(rec: Dict[str, Any]) -> int:
            n = (rec.get("hospital_name") or "").lower()
            q = name_query.lower()
            return sum(1 for t in q.split() if t in n)
        best = sorted(data, key=score, reverse=True)[0]
        return best
    except Exception:
        return {}


@st.cache_data(show_spinner=False)
def bing_news_search(org_name: str) -> List[Dict[str, Any]]:
    if not BING_SEARCH_API_KEY:
        return []
    url = "https://api.bing.microsoft.com/v7.0/news/search"
    params = {"q": f"{org_name} hospital OR health system press release", "mkt": "en-US", "count": 10, "sortBy": "Date"}
    headers = {"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY}
    try:
        data = _http_get(url, params, headers)
        return data.get("value", [])
    except Exception:
        return []


# Placeholders for private/paid sources or manual entry
@st.cache_data(show_spinner=False)
def klas_summary_placeholder() -> Dict[str, Any]:
    return {
        "note": "KLAS details require subscription. Paste summary or CSV export here.",
        "fields": ["overall_rating", "sample_quotes", "integration", "support", "usability"]
    }


@st.cache_data(show_spinner=False)
def linkedin_stub(org_name: str) -> Dict[str, Any]:
    return {
        "note": "LinkedIn public data scraping is discouraged. Use LinkedIn API/official exports or manual entry.",
        "search_hint": f"Search LinkedIn for '{org_name}' company page and capture size, locations, hiring signals."
    }


# --------------- RISK / OPPORTUNITY ENGINE ---------------
RISK_RULES: List[Tuple[str, str]] = [
    (r"wait|hold|phone|call back|call-back|queue", "Long hold times / phone queues"),
    (r"bill|billing|price|estimate|cost", "Cost transparency / price estimation issues"),
    (r"portal|login|password|app", "Portal friction (login/UX)") ,
    (r"insurance|eligibil|authorization|referral", "Eligibility/authorization pain"),
    (r"schedule|reschedule|cancel|appointment", "Scheduling friction / no-shows")
]

def score_risks_opportunities(google_details: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    risks, opps = [], []
    if not google_details:
        return risks, opps
    reviews = google_details.get("reviews") or []
    body = "\n".join([r.get("text", "") for r in reviews])
    for pattern, label in RISK_RULES:
        if re.search(pattern, body, flags=re.I):
            risks.append(label)
    rating = google_details.get("rating")
    if rating is not None:
        if rating < 3.6:
            opps.append("Patient experience uplift (reviews < 3.6)")
        elif rating >= 4.4:
            opps.append("Leverage strong PX in case studies (reviews ≥ 4.4)")
    if google_details.get("user_ratings_total", 0) > 300:
        opps.append("Large sample of patient feedback available for VoC")
    return list(sorted(set(risks))), list(sorted(set(opps)))


# --------------- ORCHESTRATOR ---------------
@st.cache_data(show_spinner=True)
def build_profile(org_name: str, location_hint: str | None = None) -> OrgProfile:
    prof = OrgProfile(query=org_name)

    # Google Places
    g = google_places_find_facility(org_name, location_hint)
    google_block = {}
    if g:
        google_block = {
            "name": g.get("name"),
            "address": g.get("formatted_address"),
            "phone": g.get("formatted_phone_number"),
            "website": g.get("website"),
            "maps_url": g.get("url"),
            "rating": g.get("rating"),
            "reviews_count": g.get("user_ratings_total"),
            "review_themes": _extract_review_themes(g.get("reviews")),
            "recent_reviews": [
                {
                    "author": r.get("author_name"),
                    "rating": r.get("rating"),
                    "time": r.get("relative_time_description"),
                    "text": textwrap.shorten(r.get("text", ""), width=240, placeholder="…")
                }
                for r in (g.get("reviews") or [])
            ]
        }
        prof.resolved_name = g.get("name")

    # CMS Care Compare
    cms = cms_hospital_general_info(prof.resolved_name or org_name)
    cms_block = {}
    if cms:
        cms_block = {
            "hospital_name": cms.get("hospital_name"),
            "type": cms.get("hospital_type"),
            "ownership": cms.get("hospital_ownership"),
            "address": f"{cms.get('address')}, {cms.get('city')}, {cms.get('state')}, {cms.get('zip_code')}",
            "emergency_services": cms.get("emergency_services"),
            "star_rating": cms.get("hospital_overall_rating"),
            "location_id": cms.get("provider_id"),
        }
        if not prof.resolved_name:
            prof.resolved_name = cms.get("hospital_name")

    # News (optional)
    news = bing_news_search(prof.resolved_name or org_name)
    news_block = [
        {
            "name": n.get("name"),
            "datePublished": n.get("datePublished"),
            "url": n.get("url"),
            "description": textwrap.shorten(n.get("description", ""), width=200, placeholder="…"),
            "provider": ", ".join([p.get("name") for p in n.get("provider", []) if p.get("name")])
        } for n in news
    ] if news else []

    # KLAS + LinkedIn placeholders
    prof.klas = klas_summary_placeholder()
    prof.linkedin = linkedin_stub(prof.resolved_name or org_name)

    # Risks & Opportunities from reviews
    risks, opps = score_risks_opportunities(g)

    prof.basics = {"input": org_name, "resolved_name": prof.resolved_name}
    prof.google = google_block
    prof.cms = cms_block
    prof.news = news_block
    prof.metrics = {}
    prof.risks = risks
    prof.opportunities = opps

    return prof


# --------------- UI ---------------
st.set_page_config(page_title="Patient Access Org Profiler", layout="wide")
st.title("🏥 Patient Access Org Profiler — Pre‑Discovery Bot (MVP)")

with st.sidebar:
    st.header("Settings")
    hint = st.text_input("City or State hint (optional)")
    st.caption("Improves match accuracy for multi-site systems.")
    st.divider()
    st.subheader("API Keys")
    st.text_input("GOOGLE_PLACES_API_KEY", value=os.getenv("GOOGLE_PLACES_API_KEY", ""), type="password")
    st.text_input("BING_SEARCH_API_KEY", value=os.getenv("BING_SEARCH_API_KEY", ""), type="password")
    st.caption("Keys are read from environment at runtime — set before starting app.")

query = st.text_input("Enter organization / facility name", placeholder="e.g., Mercy General Hospital")
run = st.button("Build Profile", type="primary")

if run and query:
    with st.spinner("Building profile…"):
        profile = build_profile(query, hint)

    col1, col2 = st.columns([1,1])

    with col1:
        st.subheader("🧭 Basics")
        st.json(profile.basics or {})

        st.subheader("📍 CMS Care Compare")
        st.json(profile.cms or {})

        st.subheader("📰 News (recent)")
        if profile.news:
            for n in profile.news:
                st.markdown(f"- **[{n['name']}]({n['url']})** — {n['provider']}  ")
                st.caption(f"{n['datePublished']}: {n['description']}")
        else:
            st.caption("No news pulled (add BING_SEARCH_API_KEY) or none found.")

    with col2:
        st.subheader("⭐ Google Reviews Snapshot")
        st.json(profile.google or {})

        st.subheader("⚠️ Risks & 🎯 Opportunities")
        st.write({"risks": profile.risks or [], "opportunities": profile.opportunities or []})

        st.subheader("📊 KLAS (placeholder)")
        st.json(profile.klas or {})

        st.subheader("💼 LinkedIn (placeholder)")
        st.json(profile.linkedin or {})

    st.divider()
    st.subheader("Raw JSON")
    st.code(profile.to_json(), language="json")

    st.download_button("Download profile JSON", data=profile.to_json().encode("utf-8"), file_name=f"{(profile.resolved_name or query).replace(' ', '_')}_profile.json", mime="application/json")

else:
    st.info("Enter an organization name and click **Build Profile** to generate a pre‑discovery dossier.")

# --------------- NEXT STEPS (dev notes in-code) ---------------
# TODOs for production:
# - Add CMS quality/star/complication datasets joins by provider_id
# - Add Medicare Cost Report pull (HCRIS) for beds, FTEs, payer mix
# - Add IRS 990 (ProPublica Nonprofit Explorer API) for nonprofits
# - Add State Hospital Association utilization reports scraper (where permitted)
# - Add robust entity resolution across multi-facility systems
# - Persist to a DB (e.g., Postgres) and add Redis caching
# - Implement typed client classes + retries + circuit breakers
# - Add OpenAI/LLM summarizer to turn raw facts into 3-sentence briefing + tailored discovery questions

