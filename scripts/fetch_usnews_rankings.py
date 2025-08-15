import requests
from bs4 import BeautifulSoup

def fetch_usnews_rankings(hospital_name):
    url = f"https://health.usnews.com/best-hospitals/search?hospital_name={hospital_name.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        # Extract relevant information
        ranking = soup.find("div", class_="ranking").text.strip()
        specialties = [specialty.text.strip() for specialty in soup.find_all("div", class_="specialty")]
        return {"ranking": ranking, "specialties": specialties}
    except Exception as e:
        return {"error": f"Failed to fetch data: {e}"}
