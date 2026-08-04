#Pulls all the Datacite Calls for the Dataset DOI's listed in cited_list100.json and puts them into DataciteCall_Results.json to be used for future cross-referencing. 
import json
import requests
from typing import Any, Dict, List


DATACITE_API = "https://api.datacite.org/dois"


def _safe_get(dct: Dict[str, Any], *keys, default=None):
    cur = dct
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _normalize_record(item: Dict[str, Any]) -> Dict[str, Any]:
    attrs = item.get("attributes", {}) or {}

    creators = []
    for c in attrs.get("creators", []) or []:
        name = c.get("name")
        if not name:
            given = c.get("givenName", "") or ""
            family = c.get("familyName", "") or ""
            name = f"{given} {family}".strip() or None
        if name:
            creators.append(name)

    titles = [t.get("title") for t in (attrs.get("titles", []) or []) if t.get("title")]
    subjects = [s.get("subject") for s in (attrs.get("subjects", []) or []) if s.get("subject")]
    descriptions = [d.get("description") for d in (attrs.get("descriptions", []) or []) if d.get("description")]
    rights = [r.get("rights") for r in (attrs.get("rightsList", []) or []) if r.get("rights")]

    return {
        "id": item.get("id"),
        "doi": attrs.get("doi"),
        "titles": titles,
        "creators": creators,
        "publisher": attrs.get("publisher"),
        "publication_year": attrs.get("publicationYear"),
        "resource_type_general": _safe_get(attrs, "types", "resourceTypeGeneral"),
        "url": attrs.get("url"),
        "published": attrs.get("published"),
        "updated": attrs.get("updated"),
        "registered": attrs.get("registered"),
        "language": attrs.get("language"),
        "rights": rights,
        "version": attrs.get("version"),
    }


def _metadata_diff(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Compare two normalized versions and return only changed fields.
    """
    tracked_fields = [
        "doi",
        "titles",
        "creators",
        "publisher",
        "publication_year",
        "resource_type_general",
        "url",
        "language",
        "rights",
        "version",
        "state",
    ]

    changes = {}
    for field in tracked_fields:
        if old.get(field) != new.get(field):
            changes[field] = {"old": old.get(field), "new": new.get(field)}
    return changes


def fetch_datacite_metadata_with_history(
    doi: str,
    timeout: int = 20,
    page_size: int = 100,
) -> Dict[str, Any]:
    """
    Fetch DataCite metadata for DOI and include all available versions/iterations.
    """
    if not doi or not doi.strip():
        raise ValueError("DOI must be a non-empty string.")

    doi = doi.strip()

    resp = requests.get(
        DATACITE_API,
        params={"query": doi, "page[size]": page_size},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()

    items = payload.get("data", []) or []
    if not items:
        raise ValueError(f"No DataCite records found for DOI query: {doi}")

    chosen = None
    doi_lower = doi.lower()
    for item in items:
        item_doi = (_safe_get(item, "attributes", "doi", default="") or "").lower()
        if item_doi == doi_lower:
            chosen = item
            break
    if chosen is None:
        chosen = items[0]

    current = _normalize_record(chosen)
    canonical_doi = current.get("doi") or doi

    versions_url = f"{DATACITE_API}/{canonical_doi}/versions"
    v_resp = requests.get(
        versions_url,
        params={"page[size]": page_size},
        timeout=timeout,
    )

    history: List[Dict[str, Any]] = []
    if v_resp.status_code == 200:
        v_payload = v_resp.json()
        v_items = v_payload.get("data", []) or []
        history = [_normalize_record(v) for v in v_items]
    else:
        history = [current]

    current_id = current.get("id")
    if current_id and all(h.get("id") != current_id for h in history):
        history.append(current)

    def _sort_key(rec: Dict[str, Any]):
        return (
            rec.get("registered") or "",
            rec.get("published") or "",
            rec.get("updated") or "",
            rec.get("id") or "",
        )

    history = sorted(history, key=_sort_key)

    changes_between_versions = []
    for i in range(1, len(history)):
        old = history[i - 1]
        new = history[i]
        changes = _metadata_diff(old, new)
        if changes:
            changes_between_versions.append(
                {
                    "from_index": i - 1,
                    "to_index": i,
                    "from_id": old.get("id"),
                    "to_id": new.get("id"),
                    "changes": changes,
                }
            )

    return {
        "query_doi": doi,
        "canonical_doi": canonical_doi,
        "current": current,
        "history": history,
        "changes_between_versions": changes_between_versions,
    }


def process_cited_dois(
    input_json_path: str = "cited_list100.json",
    output_json_path: str = "datacite_results.json",
) -> Dict[str, Any]:
    """
    Read cited_list100.json and fetch DataCite metadata history for every DOI in each record's 'doi' list.
    Save all results to output_json_path.
    """
    with open(input_json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    results: Dict[str, Any] = {}
    for rec in records:
        for doi in rec.get("doi", []) or []:
            doi_str = (doi or "").strip()
            if not doi_str:
                continue
            if doi_str in results:
                continue  # avoid duplicate API calls
            try:
                results[doi_str] = fetch_datacite_metadata_with_history(doi_str)
                print(f"Processed DOI: {doi_str}")
            except Exception as e:
                print(f"Failed DOI {doi_str}: {e}")
                results[doi_str] = {"error": str(e)}

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved results to: {output_json_path}")
    return results


if __name__ == "__main__":
    all_results = process_cited_dois(
        input_json_path="cited_list100.json",
        output_json_path="datacite_results.json",
    )
    print(f"Finished processing {len(all_results)} DOI(s).")
