import os
import sys
import requests


ADS_API_URL = "https://api.adsabs.harvard.edu/v1/search/query"
CROSSREF_API_URL = "https://api.crossref.org/works/{}"


def fetch_crossref_referenced_dois(doi):
    response = requests.get(CROSSREF_API_URL.format(doi), timeout=30)
    response.raise_for_status()

    message = response.json().get("message", {})
    references = message.get("reference", [])

    cited_dois = []
    for ref in references:
        ref_doi = ref.get("DOI")
        if ref_doi:
            cited_dois.append(ref_doi.lower())

    return cited_dois


def fetch_dataset_records_for_dois(dois):
    token = os.environ.get("ADS_API_TOKEN")
    if not token:
        raise RuntimeError("ADS_API_TOKEN environment variable is required")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    results = []
    seen = set()

    for doi in dois:
        query = f'doi:"{doi}" AND doctype:dataset'
        params = {
            "q": query,
            "fl": "id,title,doi,doctype,citation_count,bibcode,identifier"
        }

        response = requests.get(ADS_API_URL, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        docs = response.json().get("response", {}).get("docs", [])
        for doc in docs:
            key = doc.get("id") or doc.get("bibcode") or doc.get("doi")
            if key and key not in seen:
                seen.add(key)
                results.append(doc)

    return results


def fetch_dataset_citations_from_source_doi(source_doi):
    cited_dois = fetch_crossref_referenced_dois(source_doi)
    return fetch_dataset_records_for_dois(cited_dois)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python CitationTracking.py <SOURCE_DOI>")
        sys.exit(1)

    source_doi = sys.argv[1]
    result = fetch_dataset_citations_from_source_doi(source_doi)
    print(result)
