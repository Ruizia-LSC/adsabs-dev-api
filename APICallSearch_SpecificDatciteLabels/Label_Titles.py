import json
import re
import requests
from typing import Iterable, Any


def find_phrases_in_doi_metadata(
    doi: str,
    phrases: Iterable[str],
    timeout: int = 10,
    case_sensitive: bool = False,
) -> list[tuple[str, str, str, dict[str, Any] | None]]:
    """
    Query Crossref metadata for a DOI and find all occurrences of ANY phrase
    in the returned metadata JSON.

    Args:
        doi: DOI string, e.g. "10.1029/2023SW003772"
        phrases: Phrases to search for.
        timeout: HTTP timeout in seconds.
        case_sensitive: If False, performs case-insensitive matching.

    Returns:
        A list of (matched_phrase, matched_path, matched_text, matched_reference_obj) tuples.
        - matched_phrase: The phrase that matched.
        - matched_path: JSON path-like location where the match was found.
        - matched_text: Full string leaf containing the matched phrase.
        - matched_reference_obj: Full reference dict if match is inside
          $.message.reference[<index>]..., else None.
    """
    url = f"https://api.crossref.org/works/{doi}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return []

    message = payload.get("message", {})

    phrase_list = [p for p in phrases if isinstance(p, str) and p.strip()]
    if not phrase_list:
        return []

    targets = phrase_list if case_sensitive else [p.lower() for p in phrase_list]

    def _collect_matches(value, path="$"):
        current_matches = []
        # String leaf
        if isinstance(value, str):
            hay = value if case_sensitive else value.lower()
            for original, target in zip(phrase_list, targets):
                if target in hay:
                    current_matches.append((original, path, value))
            return current_matches

        # Dict node
        if isinstance(value, dict):
            for k, v in value.items():
                current_matches.extend(_collect_matches(v, f"{path}.{k}"))
            return current_matches

        # List node
        if isinstance(value, list):
            for i, item in enumerate(value):
                current_matches.extend(_collect_matches(item, f"{path}[{i}]"))
            return current_matches

        # Non-string scalar
        return current_matches

    all_raw_matches = _collect_matches(message, path="$.message")

    final_matches = []
    for original_phrase, path, text in all_raw_matches:
        matched_reference_obj = None
        m = re.match(r"^\$.message\.reference\[(\d+)\](?:\.|$)", path)
        if m:
            idx = int(m.group(1))
            refs = message.get("reference")
            if isinstance(refs, list) and 0 <= idx < len(refs):
                ref_obj = refs[idx]
                if isinstance(ref_obj, dict):
                    matched_reference_obj = ref_obj
        final_matches.append((original_phrase, path, text, matched_reference_obj))

    return final_matches


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


def load_target_titles(datacite_json_path: str) -> list[str]:
    """
    Load title values from DatacieCall_Results.json.

    Tries common title fields:
    - title
    - titles (string or list; list entries may be strings or dicts like {"title": "..."} )
    - resource_title

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

    collected = []

    for rec in records:
        if not isinstance(rec, dict):
            continue

        # Access the 'current' dictionary where titles are located
        current_data = rec.get("current", {})

        # Single-string title fields from 'current_data'
        for key in ("title", "resource_title"):
            val = current_data.get(key)
            if isinstance(val, str) and val.strip():
                collected.append(val.strip())

        # "titles" can be string, list[str], or list[dict] from 'current_data'
        titles_val = current_data.get("titles")
        if isinstance(titles_val, str):
            if titles_val.strip():
                collected.append(titles_val.strip())
        elif isinstance(titles_val, list):
            for item in titles_val:
                if isinstance(item, str) and item.strip():
                    collected.append(item.strip())
                elif isinstance(item, dict):
                    # Common shapes for DataCite-like title objects
                    for k in ("title", "value", "text"):
                        v = item.get(k)
                        if isinstance(v, str) and v.strip():
                            collected.append(v.strip())

    # Deduplicate while preserving order (case-insensitive)
    seen = set()
    unique = []
    for t in collected:
        norm = t.lower()
        if norm not in seen:
            seen.add(norm)
            unique.append(t)

    return unique


if __name__ == "__main__":
    citation_json_file = "cited_list100.json"
    datacite_json_file = "DatacieCall_Results.json"
    output_json_file = "crossref_title_matches.json"

    citation_dois = load_citation_dois(citation_json_file)
    target_titles = load_target_titles(datacite_json_file)

    print(f"Loaded {len(citation_dois)} citation DOIs from '{citation_json_file}'.")
    print(
        f"Loaded {len(target_titles)} target titles "
        f"from '{datacite_json_file}'.\n"
    )

    results = []

    for doi in citation_dois:
        # Call the modified function to get all matches for this DOI
        doi_matches = find_phrases_in_doi_metadata(
            doi, target_titles
        )

        for matched_title, location, citation_text, reference_obj in doi_matches:
            print(f"[MATCH]    DOI: {doi}")
            print(f"           Matched title: {matched_title}")
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
                    "matched_title": matched_title,
                    "matched_path": location,
                    "matched_text": citation_text,
                    "matched_reference_object": reference_obj,
                }
            )

    with open(output_json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} matches to '{output_json_file}'.")
