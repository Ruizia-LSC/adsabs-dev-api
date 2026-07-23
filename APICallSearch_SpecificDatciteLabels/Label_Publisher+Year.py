import json
import requests
from typing import Any


def crossref_contains_publisher_and_year(
    doi: str,
    publisher: str,
    publication_year: int | str,
    timeout: int = 10,
    case_sensitive: bool = False,
) -> tuple[bool, str | None, str | None]:
    """
    Query Crossref metadata for a DOI and check whether BOTH:
      - publisher
      - publication year
    are present in the returned metadata.

    Returns:
        (matched, matched_publisher_text, matched_year_text)
    """
    url = f"https://api.crossref.org/works/{doi}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return False, None, None

    message = payload.get("message", {})
    if not isinstance(message, dict):
        return False, None, None

    # Normalize inputs
    pub_input = (publisher or "").strip()
    if not pub_input:
        return False, None, None

    year_input = str(publication_year).strip()
    if not year_input:
        return False, None, None

    # Crossref publisher field
    crossref_publisher = message.get("publisher")
    if not isinstance(crossref_publisher, str):
        return False, None, None

    pub_hay = crossref_publisher if case_sensitive else crossref_publisher.lower()
    pub_needle = pub_input if case_sensitive else pub_input.lower()
    publisher_match = pub_needle in pub_hay

    # Try to extract publication year from common Crossref date fields
    def extract_year(msg: dict[str, Any]) -> str | None:
        # Priority order: published-print, published-online, issued, created
        for key in ("published-print", "published-online", "issued", "created"):
            date_obj = msg.get(key)
            if not isinstance(date_obj, dict):
                continue
            parts = date_obj.get("date-parts")
            if (
                isinstance(parts, list)
                and parts
                and isinstance(parts[0], list)
                and parts[0]
            ):
                first = parts[0][0]
                if isinstance(first, (int, str)):
                    y = str(first).strip()
                    if y:
                        return y
        return None

    crossref_year = extract_year(message)
    year_match = crossref_year == year_input if crossref_year else False

    if publisher_match and year_match:
        return True, crossref_publisher, crossref_year

    return False, crossref_publisher if publisher_match else None, crossref_year if year_match else None


def load_citation_dois(json_path: str) -> list[str]:
    """
    Load all citation_doi values from every entry in the given JSON file.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    dois = []
    for record in records:
        dois.extend(record.get("citation_doi", []))
    return dois


def load_target_publisher_year_pairs(datacite_json_path: str) -> list[dict[str, Any]]:
    """
    Load (publisher, publication_year) pairs from DatacieCall_Results.json.

    Handles both top-level list and top-level dict with nested records.
    """
    with open(datacite_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize records into a list of dicts
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        found_records = False
        for key in ("results", "records", "items", "data"):
            if isinstance(data.get(key), list):
                records = data[key]
                found_records = True
                break
        if not found_records:
            records = [v for v in data.values() if isinstance(v, dict)]
    else:
        records = []

    collected: list[dict[str, Any]] = []

    for rec in records:
        if not isinstance(rec, dict):
            continue

        publisher = rec.get("publisher")
        publication_year = rec.get("publication_year")

        if isinstance(publisher, str) and publisher.strip() and publication_year is not None:
            collected.append(
                {
                    "publisher": publisher.strip(),
                    "publication_year": str(publication_year).strip(),
                }
            )

    # Deduplicate pairs while preserving order
    seen = set()
    unique = []
    for item in collected:
        key = (item["publisher"].lower(), item["publication_year"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


if __name__ == "__main__":
    citation_json_file = "cited_list100.json"
    datacite_json_file = "DatacieCall_Results.json"
    output_json_file = "crossref_publisher_year_matches.json"

    citation_dois = load_citation_dois(citation_json_file)
    target_pairs = load_target_publisher_year_pairs(datacite_json_file)

    print(f"Loaded {len(citation_dois)} citation DOIs from '{citation_json_file}'.")
    print(
        f"Loaded {len(target_pairs)} target (publisher, publication_year) pairs "
        f"from '{datacite_json_file}'.\n"
    )

    results = []

    for doi in citation_dois:
        for pair in target_pairs:
            matched, matched_publisher, matched_year = crossref_contains_publisher_and_year(
                doi=doi,
                publisher=pair["publisher"],
                publication_year=pair["publication_year"],
            )

            if matched:
                print(f"[MATCH]    DOI: {doi}")
                print(f"           Publisher: {matched_publisher}")
                print(f"           Publication year: {matched_year}")
                print()

                results.append(
                    {
                        "citation_doi": doi,
                        "matched_publisher": matched_publisher,
                        "matched_publication_year": matched_year,
                        "target_publisher": pair["publisher"],
                        "target_publication_year": pair["publication_year"],
                    }
                )
                # Stop after first pair match for this DOI
                break

    with open(output_json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} matches to '{output_json_file}'.")
