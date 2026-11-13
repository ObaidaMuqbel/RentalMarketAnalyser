import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin
import csv
from pathlib import Path

url = "https://www.dexters.co.uk/property-lettings/properties-to-rent-in-london"

response = requests.get(url, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
listings = soup.select("li.result[data-property-id]")

if not listings:
    raise RuntimeError("No listings found. The page may have changed or blocked access.")

print(f"Listings found on this page: {len(listings)}")

collected_at = datetime.now(timezone.utc).isoformat()

records = []

for listing in listings:
    location = listing.select_one(".address-area-post")
    price = listing.select_one(".price-qualifier")
    bedrooms = listing.select_one(".Bedrooms")
    bathrooms = listing.select_one(".Bathrooms")
    link = listing.select_one("h2 a")

    record = {
        "listing_id": listing.get("data-property-id"),
        "location": location.get_text(strip=True) if location else None,
        "rent_pcm": float(price["data-price"])
        if price and price.get("data-price") else None,
        "bedrooms": int(bedrooms.get_text(strip=True).split()[0])
        if bedrooms else None,
        "bathrooms": int(bathrooms.get_text(strip=True).split()[0])
        if bathrooms else None,
        "source": "Dexters",
        "source_url": urljoin(url, link["href"])
        if link and link.get("href") else None,
        "collected_at": collected_at,
    }

    records.append(record)

for record in records[:3]:
    print(record)

project_root = Path(__file__).resolve().parent.parent
output_folder = project_root / "data" / "raw"
output_folder.mkdir(parents=True, exist_ok=True)

timestamp = collected_at.replace(":", "-")
output_file = output_folder / f"dexters_test_{timestamp}.csv"

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)

print(f"\nSaved {len(records)} records to: {output_file}")