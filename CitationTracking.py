import os
import sys
import requests


API_URL = "https://api.adsabs.harvard.edu/v1/search/query"


def fetch_by_doi(doi, doctype=None):
    token = os.environ.get("ADS_API_TOKEN")
    if not token:
        raise RuntimeError("ADS_API_TOKEN environment variable is required")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    query = f'doi:"{doi}"'
    if doctype:
        query += f" AND doctype:{doctype}"

    params = {
        "q": query,
        "fl": "id,title,doi,citation_count"
    }

    response = requests.get(API_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python CitationTracking.py <DOI> [DOCTYPE]")
        sys.exit(1)

    doi = sys.argv[1]
    doctype = sys.argv[2] if len(sys.argv) > 2 else None

    result = fetch_by_doi(doi, doctype)
    print(result)
