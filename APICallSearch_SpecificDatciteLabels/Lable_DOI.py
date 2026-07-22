import json
import re
import requests
from typing import Iterable, Any


def doi_metadata_contains_any_phrase(
    doi: str,
    phrases: Iterable[str],
    timeout: int = 10,
    case_sensitive: bool = False,
) -> tuple[bool, str | None, str | None, str | None, dict[str, Any] | None]:
    """
    Query Crossref metadata for a DOI and check whether ANY phrase exists anywhere
    in the returned metadata JSON.

    Args:
        doi: DOI string, e.g. "10.1029/2023SW003772"
        phrases: Phrases to search for.
        timeout: HTTP timeout in seconds.
        case_sensitive: If False, performs case-insensitive matching.

    Returns:
        (matched, matched_phrase, matched_path, matched_text, matched_reference_obj)
        - matched: True if any phrase found
        - matched_phrase: phrase that matched first
        - matched_path: JSON path-like location where first match was found, else None
        - matched_text: full string leaf containing the matched phrase, else None
        - matched_reference_obj: full reference dict if match is inside
          $.message.reference[<index>]..., else None
    """
    url = f"https://api.crossref.org/works/{doi}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return False, None, None, None, None

    message = payload.get("message", {})

    phrase_list = [p for p in phrases if isinstance(p, str) and p.strip()]
    if not phrase_list:
        return False, None, None, None, None

    targets = phrase_list if case_sensitive else [p.lower() for p in phrase_list]

    def _contains(value, path="$"):
        # String leaf
        if isinstance(value, str):
            hay = value if case_sensitive else value.lower()
            for original, target in zip(phrase_list, targets):
                if target in hay:
                    return True, original, path, value
            return False, None, None, None

        # Dict node
        if isinstance(value, dict):
            for k, v in value.items():
                found, found_phrase, found_path, found_text = _contains(v, f"{path}.{k}")
                if found:
                    return True, found_phrase, found_path, found_text
            return False, None, None, None

        # List node
        if isinstance(value, list):
            for i, item in enumerate(value):
                found, found_phrase, found_path, found_text = _contains(item, f"{path}[{i}]")
                if found:
                    return True, found_phrase, found_path, found_text
            return False, None, None, None

        # Non-string scalar
        return False, None, None, None

    matched, matched_phrase, matched_path, matched_text = _contains(message, path="$.message")

    if not matched:
        return False, None, None, None, None

    # If match is under $.message.reference[<idx>]..., return that full reference object.
    matched_reference_obj = None
    if matched_path:
        m = re.match(r"^\$\.message\.reference\[(\d+)\](?:\.|$)", matched_path)
        if m:
            idx = int(m.group(1))
            refs = message.get("reference")
            if isinstance(refs, list) and 0 <= idx < len(refs):
                ref_obj = refs[idx]
                if isinstance(ref_obj, dict):
                    matched_reference_obj = ref_obj

    return matched, matched_phrase, matched_path, matched_text, matched_reference_obj


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
    output_json_file = "crossref_doi_matches.json"

    citation_dois = load_citation_dois(citation_json_file)
    target_dois = load_target_dois(datacite_json_file)

    print(f"Loaded {len(citation_dois)} citation DOIs from '{citation_json_file}'.")
    print(
        f"Loaded {len(target_dois)} target DOIs "
        f"(query_doi/canonical_doi/doi) from '{datacite_json_file}'.\n"
    )

    results = []

    for doi in citation_dois:
        matched, matched_doi, location, citation_text, reference_obj = doi_metadata_contains_any_phrase(
            doi, target_dois
        )

        if matched:
            print(f"[MATCH]    DOI: {doi}")
            print(f"           Matched target DOI: {matched_doi}")
            print(f"           Location: {location}")
            print(f"           Citation text: {citation_text}")

            if reference_obj is not None:
                print("           Full reference object:")
                print(
                    "           "
                    + json.dumps(reference_obj, ensure_ascii=False, indent=2).replace("\n", "\n           ")
                )
            print()

            results.append(
                {
                    "citation_doi": doi,
                    "matched_target_doi": matched_doi,
                    "matched_path": location,
                    "matched_text": citation_text,
                    "matched_reference_object": reference_obj,
                }
            )

    with open(output_json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} matches to '{output_json_file}'.")
