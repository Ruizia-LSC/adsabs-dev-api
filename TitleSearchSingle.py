import json
import requests


def doi_metadata_contains_phrase(
    doi: str,
    phrase: str,
    timeout: int = 10,
    case_sensitive: bool = False,
) -> tuple[bool, str | None]:
    """
    Query Crossref metadata for a DOI and check whether a phrase exists anywhere
    in the returned metadata JSON.

    Args:
        doi: DOI string, e.g. "10.1029/2023SW003772"
        phrase: Phrase to search for.
        timeout: HTTP timeout in seconds.
        case_sensitive: If False, performs case-insensitive matching.

    Returns:
        (matched, matched_path)
        - matched: True if phrase found
        - matched_path: JSON path-like location where first match was found, else None
    """
    url = f"https://api.crossref.org/works/{doi}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return False, None

    message = payload.get("message", {})

    target = phrase if case_sensitive else phrase.lower()

    def _contains(value, path="$"):
        # String leaf
        if isinstance(value, str):
            hay = value if case_sensitive else value.lower()
            if target in hay:
                return True, path
            return False, None

        # Dict node
        if isinstance(value, dict):
            for k, v in value.items():
                found, found_path = _contains(v, f"{path}.{k}")
                if found:
                    return True, found_path
            return False, None

        # List node
        if isinstance(value, list):
            for i, item in enumerate(value):
                found, found_path = _contains(item, f"{path}[{i}]")
                if found:
                    return True, found_path
            return False, None

        # Non-string scalar
        return False, None

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


if __name__ == "__main__":
    json_file = "cited_list100.json"
    search = "Binned TIMED/SEE VUV irradiance data"

    citation_dois = load_citation_dois(json_file)
    print(f"Loaded {len(citation_dois)} citation DOIs from '{json_file}'.\n")

    for doi in citation_dois:
        matched, location = doi_metadata_contains_phrase(doi, search)
        if matched:
            print(f"[MATCH]    DOI: {doi}")
            print(f"           Location: {location}\n")
        else:
            print(f"[no match] DOI: {doi}")
