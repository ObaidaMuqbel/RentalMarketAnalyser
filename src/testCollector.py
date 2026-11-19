import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# Download a page and turn its HTML into searchable elements.
def get_page(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


# Extract property details from one results page.
def extract_records(page, page_url, collected_at):
    listings = page.select("li.result[data-property-id]")

    if not listings:
        raise ValueError("No listings found. Check the website or page structure.")

    records = []

    for listing in listings:
        # Find the HTML elements containing the property details.
        location_element = listing.select_one(".address-area-post")
        rent_element = listing.select_one(".price-qualifier")
        bedrooms_element = listing.select_one(".Bedrooms")
        bathrooms_element = listing.select_one(".Bathrooms")
        link_element = listing.select_one("h2 a")
        description_element = listing.select_one(".result-entry")

        # Start with missing values instead of assuming a value of zero.
        location = None
        neighbourhood = None
        postcode_district = None
        rent_pcm = None
        bedrooms = None
        bathrooms = None
        source_url = None

        # Separate the area name from the postcode district.
        if location_element:
            location = location_element.get_text(strip=True)
            parts = location.rsplit(",", 1)
            neighbourhood = parts[0].strip()

            if len(parts) == 2:
                postcode_district = parts[1].strip()

        # Convert rent and room counts into numbers.
        if rent_element and rent_element.get("data-price"):
            rent_pcm = float(rent_element["data-price"])

        if bedrooms_element:
            bedrooms_text = bedrooms_element.get_text(strip=True)
            bedrooms = int(bedrooms_text.split()[0])

        if bathrooms_element:
            bathrooms_text = bathrooms_element.get_text(strip=True)
            bathrooms = int(bathrooms_text.split()[0])

        # Convert the property's relative link into a full URL.
        if link_element and link_element.get("href"):
            source_url = urljoin(page_url, link_element["href"])

        # Read the letting status from the listing's HTML classes.
        classes = listing.get("class", [])

        if "let" in classes:
            listing_status = "let"
        elif "to-let" in classes:
            listing_status = "to-let"
        else:
            listing_status = "unknown"

        # Check whether the description mentions a short let.
        description = ""

        if description_element:
            description = description_element.get_text(" ", strip=True)

        short_let_mentioned = bool(
            re.search(
                r"\bshort[\s-]+let\b",
                description,
                flags=re.IGNORECASE,
            )
        )

        # Store this property's details in one dictionary.
        record = {
            "listing_id": listing.get("data-property-id"),
            "location": location,
            "neighbourhood": neighbourhood,
            "postcode_district": postcode_district,
            "rent_pcm": rent_pcm,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "listing_status": listing_status,
            "short_let_mentioned": short_let_mentioned,
            "source": "Dexters",
            "source_url": source_url,
            "collected_at": collected_at,
        }

        records.append(record)

    return records


# Remove repeated listing IDs within this collection run.
def remove_duplicates(records):
    unique_records = []
    seen_ids = set()

    for record in records:
        listing_id = record["listing_id"]

        if not listing_id:
            raise ValueError("A listing is missing its ID.")

        if listing_id not in seen_ids:
            unique_records.append(record)
            seen_ids.add(listing_id)

    return unique_records


# Save the collected records into a new CSV file.
def save_records(records, collected_at):
    project_folder = Path(__file__).resolve().parent.parent
    output_folder = project_folder / "data" / "raw"
    output_folder.mkdir(parents=True, exist_ok=True)

    timestamp = collected_at.replace(":", "-")
    output_file = output_folder / f"dexters_test_{timestamp}.csv"

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    print(f"Saved {len(records)} records to: {output_file}")


# Control the order of the collection steps.
def main():
    url = (
        "https://www.dexters.co.uk/"
        "property-lettings/properties-to-rent-in-london"
    )
    collected_at = datetime.now(timezone.utc).isoformat()

    # Collect the first page.
    first_page = get_page(url)
    records = extract_records(first_page, url, collected_at)

    print(f"Page one records: {len(records)}")

    # Follow the Next link and collect the second page.
    next_link = first_page.select_one(".pagination-next a")

    if next_link and next_link.get("href"):
        next_url = urljoin(url, next_link["href"])
        second_page = get_page(next_url)
        second_records = extract_records(
            second_page, next_url, collected_at
        )

        print(f"Page two records: {len(second_records)}")
        records.extend(second_records)
    else:
        print("No second page found.")

    # Remove duplicates before saving the combined results.
    total_records = len(records)
    records = remove_duplicates(records)

    print(f"Records before deduplication: {total_records}")
    print(f"Duplicates removed: {total_records - len(records)}")
    print(f"Unique records: {len(records)}")

    save_records(records, collected_at)


# Run main only when this file is executed directly.
if __name__ == "__main__":
    main()