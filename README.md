# Healthcare Organization Discovery Profiler

This application is a **Streamlit web app** and **local tool** to profile healthcare organizations.
It combines CMS Hospital General Information data with Google Reviews, hospital rankings, and
web-scraped review sources.

---

## Features
- **Search healthcare organizations** by name with fuzzy matching.
- **CMS Data Integration**: Uses the Hospital General Information dataset from CMS.
- **Google Reviews Integration**: Pulls live ratings & reviews from Google Places API.
- **Hospital Rankings**: Scrapes/collects USA Today and other public ranking data.
- **Multiple Review Sources**: Can extend to RateMDs, Healthgrades, Yelp, and more.
- **Progress tracking** while scraping data.
- **Local CSV caching** to avoid repeated downloads.

---

## Requirements
- Python 3.9+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

---

## Setup Instructions

1. **Download CMS Data**
   - Get the latest **Hospital General Information** CSV from:
     [CMS Data Portal](https://data.cms.gov/provider-data/dataset/xubh-q36u)
   - Place it in the root folder as `Hospital_General_Information.csv`.

2. **Google Reviews API Key (Optional but Recommended)**
   - Create a Google Cloud project: https://console.cloud.google.com/
   - Enable the **Places API** and **Maps JavaScript API**.
   - Create an API key and put it in a `.env` file:
     ```
     GOOGLE_API_KEY=YOUR_API_KEY
     ```

3. **Run Locally**
   ```bash
   streamlit run profiler.py
   ```

4. **Run in Bare Mode (No Streamlit UI)**
   ```bash
   python profiler.py
   ```

---

## Notes
- Google Reviews requires an API key.
- Without API keys, the app still works with CMS and public scraped ranking data.
- Slow scraping is expected if API keys are not used — progress bar will be shown.

---

## Example Search
If you run:
```
UCSF Medical Center
```
You’ll get:
- CMS Profile (location, ratings, bed count, etc.)
- Google Reviews (rating & sample reviews)
- Public ranking info from USA Today
- Any extra review data we can scrape

---

## File Structure
```
org_profiler/
├── profiler.py               # Main Streamlit app
├── requirements.txt          # Dependencies
├── Hospital_General_Information.csv  # CMS data (you provide)
├── utils/                    # Helper scripts
├── README.md                 # This file
```

---

## License
MIT License
