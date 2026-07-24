#Pulls the whole Crossref API data for the cited_list100.json file and searches for an input keyword. 
import json
import requests

def fetch_crossref_message(
    doi: str,
    timeout: int = 10,
):
    """
    Fetch the Crossref message payload for a DOI.

    Args:
        doi: DOI string, e.g. "10.1029/2023SW003772"
        timeout: HTTP timeout in seconds.

    Returns:
        The Crossref 'message' dict, or None if the request/parsing fails.
    """
    url = f"https://api.crossref.org/works/{doi}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return None

    return payload.get("message", {})

def get_value_at_path(data, path: str):
    """
    Resolve a simple JSON-path-like string such as:
      $.message.title[0]
      $.message.reference[3].article-title
    """
    if not path.startswith("$."):
        return None

    current = data
    parts = path[2:].split(".")

    for part in parts:
        while "[" in part:
            field, rest = part.split("[", 1)
            if field:
                if not isinstance(current, dict):
                    return None
                current = current.get(field)
            idx_str, remainder = rest.split("]", 1)
            if not isinstance(current, list):
                return None
            current = current[int(idx_str)]
            part = remainder

        if part:
            if not isinstance(current, dict):
                return None
            current = current.get(part)

    return current

def extract_full_citation_from_match(message: dict, match_path: str) -> str | None:
    """
    Return the full citation context for a matched phrase.
    If the match is inside a Crossref reference entry, return that whole entry.
    Otherwise return the matched field value.
    """
    reference_marker = "$.message.reference["
    if match_path.startswith(reference_marker):
        end = match_path.find("]", len(reference_marker))
        if end != -1:
            ref_index = int(match_path[len(reference_marker):end])
            references = message.get("reference", [])
            if 0 <= ref_index < len(references):
                return json.dumps(references[ref_index], indent=2, ensure_ascii=False)

    value = get_value_at_path({"message": message}, match_path)
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    if value is not None:
        return str(value)
    return None

def find_phrase_in_message(
    message: dict,
    phrase: str,
    case_sensitive: bool = False,
) -> tuple[bool, str | None, str | None]:
    """
    Search a Crossref message dict for a phrase and return both the location
    and the full citation context where it was found.

    Returns:
        (matched, matched_path, citation_text)
    """

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

    matched, matched_path = _contains(message, path="$.message")
    if not matched or not matched_path:
        return False, None, None

    citation_text = extract_full_citation_from_match(message, matched_path)
    return True, matched_path, citation_text


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
    search = "Gaia EDR3"

    citation_dois = load_citation_dois(json_file)
    print(f"Loaded {len(citation_dois)} citation DOIs from '{json_file}'.\n")

    no_match_dois = []

    for doi in citation_dois:
        message = fetch_crossref_message(doi)
        if not message:
            no_match_dois.append(doi)
            continue

        matched, location, citation_text = find_phrase_in_message(message, search)
        if matched:
            print(f"[MATCH]    DOI: {doi}")
            print(f"           Location: {location}\n")
            if citation_text:
                print("           Full citation:")
                print(citation_text)
                print()
        else:
            no_match_dois.append(doi)

    print(f"\nDOIs with no match for '{search}': {len(no_match_dois)}")
    for doi in no_match_dois:
        print(f"- {doi}")
