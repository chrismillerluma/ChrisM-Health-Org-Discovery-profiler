# profiler.py

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
import json
from datetime import datetime
import time
import sys

# ==============================
# Configuration
# ==============================
CMS_BACKUP_FILE = "cms_hospitals_backup.csv"

# Optional APIs (set API_KEY = None to skip)
BRIGHTLOCAL_API_KEY = None
HEALTHGRADES_API_KEY = None
VITALS_API_KEY = None
RIBBON_API_KEY = None

# ==============================
# Helper Functions
# ==============================

def log(msg):
    """Simple terminal-style logger with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def load_cms_data():
    """Load CMS data from local backup CSV."""
    try:
        df = pd.read_csv(CMS_BACKUP_FILE, dtype=str)
        log(f"Loaded CMS data: {len(df)} records")
        return df
    except Exception as e:
        log(f"Failed to load CMS data: {e}")
        return pd.DataFrame()

def find_best_match(name, df):
    """Use RapidFuzz to find the best matching organization."""
    choices = df['Provider Name'].tolist()
    result = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio, score_cutoff=50)
    if result:
        match_name, score, idx = result
        log(f"Best match: {match_name} (score {score})")
        return df.iloc[idx]
    else:
        log("No match found")
        return None

def scrape_google_reviews(org_name):
    """Simulated Google reviews scraping (for demo, no API key required)."""
    log(f"Fetching Google reviews for '{org_name}' ...")
    # Placeholder: Replace with actual scraping if allowed
    time.sleep(2)
    reviews = [
        {"source": "Google", "rating": 5, "text": "Excellent care and staff."},
        {"source": "Google", "rating": 2, "text": "Long wait times, but competent doctors."}
    ]
    log(f"Fetched {len(reviews)} Google reviews")
    return reviews

def scrape_yelp_reviews(org_name):
    """Simulated Yelp reviews scraping."""
    log(f"Fetching Yelp reviews for '{org_name}' ...")
    time.sleep(2)
    reviews = [
        {"source": "Yelp", "rating": 4, "text": "Friendly staff and clean facility."},
        {"source": "Yelp", "rating": 1, "text": "Parking is terrible."}
    ]
    log(f"Fetched {len(reviews)} Yelp reviews")
    return reviews

def scrape_ratemd_reviews(org_name):
    """Simulated RateMDs reviews scraping."""
    log(f"Fetching RateMDs reviews for '{org_name}' ...")
    time.sleep(2)
    reviews = [
        {"source": "RateMDs", "rating": 3, "text": "Average experience, nurses helpful."},
        {"source": "RateMDs", "rating": 5, "text": "Doctors are top-notch."}
    ]
    log(f"Fetched {len(reviews)} RateMDs reviews")
    return reviews

def fetch_news(org_name):
    """Simulated news search."""
    log(f"Fetching news articles for '{org_name}' ...")
    time.sleep(1)
    news = [
        {"title": f"{org_name} receives national award", "url": "https://example.com/news1"},
        {"title": f"Patients complain about long wait times at {org_name}", "url": "https://example.com/news2"}
    ]
    log(f"Fetched {len(news)} news articles")
    return news

def aggregate_report(org_data, reviews, news):
    """Build a report dictionary."""
    report = {
        "organization": org_data['Provider Name'] if org_data is not None else "Unknown",
        "address": org_data.get('Address', 'N/A') if org_data is not None else 'N/A',
        "city": org_data.get('City', 'N/A') if org_data is not None else 'N/A',
        "state": org_data.get('State', 'N/A') if org_data is not None else 'N/A',
        "cms_info": org_data.to_dict() if org_data is not None else {},
        "reviews": reviews,
        "news": news,
        "generated_at": datetime.now().isoformat()
    }
    return report

def save_report(report):
    """Save aggregated report to JSON."""
    file_name = f"{report['organization'].replace(' ', '_')}_report.json"
    with open(file_name, "w") as f:
        json.dump(report, f, indent=2)
    log(f"Report saved to {file_name}")

# ==============================
# Main Execution
# ==============================

def main():
    log("Healthcare Organization Discovery Profiler")
    
    df_cms = load_cms_data()
    
    org_name_input = input("Enter Organization Name or Vendor: ").strip()
    if not org_name_input:
        log("No organization name entered. Exiting.")
        return
    
    org_data = find_best_match(org_name_input, df_cms)
    
    reviews = []
    reviews.extend(scrape_google_reviews(org_name_input))
    reviews.extend(scrape_yelp_reviews(org_name_input))
    reviews.extend(scrape_ratemd_reviews(org_name_input))
    
    news = fetch_news(org_name_input)
    
    report = aggregate_report(org_data, reviews, news)
    
    save_report(report)
    
    log("Profiler execution completed successfully.")

if __name__ == "__main__":
    main()
