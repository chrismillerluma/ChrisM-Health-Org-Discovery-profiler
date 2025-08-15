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
Notes: 
Using uv pip install.
Using Python 3.13.5 environment at /home/adminuser/venv
Installed 40 packages in 102ms
 + altair==5.5.0
 + attrs==25.3.0
 + beautifulsoup4==4.13.4
 + blinker==1.9.0
 + cachetools==6.1.0
 + certifi==2025.8.3
 + charset-normalizer==3.4.3
 + click==8.2.1
 + gitdb==4.0.12 
 + gitpython==3.1.45
 + idna==3.10
 + jinja2==3.1.6
 + jsonschema==4.25.0
 + jsonschema-specifications==2025.4.1
 + markupsafe==3.0.2
 + narwhals==2.1.2
 + numpy==2.3.2
 + packaging==25.0
 + pandas==2.3.1
 + pillow==11.3.0
 + protobuf==6.32.0
 + pyarrow==21.0.0
 + pydeck==0.9.1
 + python-dateutil==2.9.0.post0
 + pytz==2025.2
 + rapidfuzz==3.13.0
 + referencing==0.36.2
 + requests==2.32.4
 + rpds-py==0.27.0
 + six==1.17.0
 + smmap==5.0.2
 + soupsieve==2.7
 + streamlit==1.48.1
 + tenacity==9.1.2
 + toml==0.10.2
 + tornado==6.5.2
 + typing-extensions==4.14.1
 + tzdata==2025.2
 + urllib3==2.5.0
 + watchdog==6.0.0
 + Streamlit==1.48.1
 + markdown-it-py==4.0.0
 + mdurl==0.1.2
 + pygments==2.19.2
 + rich==14.1.0

## License
MIT License
