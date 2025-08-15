import requests
from bs4 import BeautifulSoup

def fetch_yelp_reviews(hospital_name, location="San Francisco, CA", limit=5):
    query = f"{hospital_name} {location} reviews"
    url = f"https://www.yelp.com/search?find_desc={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        reviews = []
        for review in soup.find_all("p", class_="comment__09f24__gu0rG"):
            reviews.append(review.text.strip())
            if len(reviews) >= limit:
                break
        return reviews
    except Exception as e:
        return [f"Failed to fetch reviews: {e}"]
