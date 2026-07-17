import requests

DATACITE_COMMONS_BASE = "https://api.datacite.org/dois/"


def get_datacite_citations(doi: str) -> dict:
    """
    Look up citations attributed to a data/software DOI on the DataCite side.

    The human-readable page for a DOI is:
        https://commons.datacite.org/doi.org/<DOI>

    This function queries the DataCite REST API to retrieve citation metadata
    for the given DOI, including any works that cite it.

    Args:
        doi: The DOI string, e.g. "10.5281/zenodo.10870579"

    Returns:
        A dict with:
            - "doi":          the queried DOI
            - "commons_url":  the DataCite Commons URL for the record
            - "title":        title of the dataset/software (str or None)
            - "citations":    list of citing works (may be empty)
            - "raw":          full API response payload
    """
    commons_url = f"https://commons.datacite.org/doi.org/{doi}"
    api_url = f"{DATACITE_COMMONS_BASE}{doi}"

    response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data", {})
    attributes = data.get("attributes", {})

    # Extract title
    titles = attributes.get("titles", [])
    title = titles[0].get("title") if titles else None

    # Extract citations from relatedIdentifiers where relationType == "IsCitedBy"
    related = attributes.get("relatedIdentifiers", [])
    citations = [
        {
            "relatedIdentifier": r.get("relatedIdentifier"),
            "relatedIdentifierType": r.get("relatedIdentifierType"),
            "relationType": r.get("relationType"),
        }
        for r in related
        if r.get("relationType", "").lower() == "iscitedby"
    ]

    return {
        "doi": doi,
        "commons_url": commons_url,
        "title": title,
        "citations": citations,
        "raw": payload,
    }


def print_citations(doi: str) -> None:
    """Fetch and print citation information for the given DOI."""
    print(f"Querying DataCite for DOI: {doi}")
    print(f"DataCite Commons URL: https://commons.datacite.org/doi.org/{doi}\n")

    result = get_datacite_citations(doi)

    print(f"Title   : {result['title']}")
    print(f"Citations found (IsCitedBy): {len(result['citations'])}")

    if result["citations"]:
        for i, cite in enumerate(result["citations"], start=1):
            id_type = cite.get("relatedIdentifierType", "")
            identifier = cite.get("relatedIdentifier", "")
            print(f"  [{i}] {id_type}: {identifier}")
    else:
        print("  No citations recorded on the DataCite side.")


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Replace with any DOI you want to look up
    example_doi = "10.5281/zenodo.10870579"
    print_citations(example_doi)
