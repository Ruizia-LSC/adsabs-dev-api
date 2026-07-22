import json
import requests
from typing import Iterable


def doi_metadata_contains_any_phrase(
    doi: str,
    phrases: Iterable[str],
    timeout: int = 10,
    case_sensitive: bool = False,
) -> tuple[bool, str | None, str | None]:
    """
    Query Crossref metadata for a DOI and check whether ANY phrase exists anywhere
    in the returned metadata JSON.

    Args:
        doi: DOI string, e.g. "10.1029/2023SW003772"
        phrases: Phrases to search for.
        timeout: HTTP timeout in seconds.
        case_sensitive: If False, performs case-insensitive matching.

    Returns:
        (matched, matched_phrase, matched_path)
        - matched: True if any phrase found
        - matched_phrase: phrase that matched first
        - matched_path: JSON path-like location where first match was found, else None
    """
    url = f"https://api.crossref.org/works/{doi}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return False, None, None

    message = payload.get("message", {})

    phrase_list = [p for p in phrases if isinstance(p, str) and p.strip()]
    if not phrase_list:
        return False, None, None

    targets = phrase_list if case_sensitive else [p.lower() for p in phrase_list]

    def _contains(value, path="$"):
        # String leaf
        if isinstance(value, str):
            hay = value if case_sensitive else value.lower()
            for original, target in zip(phrase_list, targets):
                if target in hay:
                    return True, original, path
            return False, None, None

        # Dict node
        if isinstance(value, dict):
            for k, v in value.items():
                found, found_phrase, found_path = _contains(v, f"{path}.{k}")
                if found:
                    return True, found_phrase, found_path
            return False, None, None

        # List node
        if isinstance(value, list):
            for i, item in enumerate(value):
                found, found_phrase, found_path = _contains(item, f"{path}[{i}]")
                if found:
                    return True, found_phrase, found_path
            return False, None, None

        # Non-string scalar
        return False, None, None

    return _contains(message, path="$.message")


def load_citation_dois(json_path: str) -> list[str]:
    """
    Load all citation_doi values from every entry in the given JSON file.

    Args:
        json_path: Path to the JSON file (e.g. 'cited_list100.json').

    Returns:
        A flat list of DOI strings gathered from every entry's 'citation_doi' field.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    dois = []
    for record in records:
        dois.extend(record.get("citation_doi", []))
    return dois


def load_target_dois(datacite_json_path: str) -> list[str]:
    """
    Load all DOI values from DatacieCall_Results.json fields:
    - query_doi
    - canonical_doi
    - doi

    Handles both top-level list and top-level dict with nested records.
    """
    with open(datacite_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize records into a list of dicts
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # If it's a dict, try common containers first, then fallback to the dict itself
        for key in ("results", "records", "items", "data"):
            if isinstance(data.get(key), list):
                records = data[key]
                break
        else:
            records = [data]
    else:
        records = []

    collected = []

    for rec in records:
        if not isinstance(rec, dict):
            continue

        for key in ("query_doi", "canonical_doi", "doi"):
            val = rec.get(key)

            if isinstance(val, str):
                if val.strip():
                    collected.append(val.strip())
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        collected.append(item.strip())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for d in collected:
        norm = d.lower()
        if norm not in seen:
            seen.add(norm)
            unique.append(d)

    return unique


if __name__ == "__main__":
    citation_json_file = "cited_list100.json"
    datacite_json_file = "DatacieCall_Results.json"

    citation_dois = load_citation_dois(citation_json_file)
    target_dois = load_target_dois(datacite_json_file)

    print(f"Loaded {len(citation_dois)} citation DOIs from '{citation_json_file}'.")
    print(
        f"Loaded {len(target_dois)} target DOIs "
        f"(query_doi/canonical_doi/doi) from '{datacite_json_file}'.\n"
    )

    for doi in citation_dois:
        matched, matched_doi, location = doi_metadata_contains_any_phrase(doi, target_dois)
        if matched:
            print(f"[MATCH]    DOI: {doi}")
            print(f"           Matched target DOI: {matched_doi}")
            print(f"           Location: {location}\n")
