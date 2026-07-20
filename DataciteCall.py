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
        "subjects": subjects,
        "descriptions": descriptions,
        "url": attrs.get("url"),
        "published": attrs.get("published"),
        "updated": attrs.get("updated"),
        "registered": attrs.get("registered"),
        "language": attrs.get("language"),
        "rights": rights,
        "version": attrs.get("version"),
        "state": attrs.get("state"),
        "raw": item,
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
        "subjects",
        "descriptions",
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

    Uses:
      - https://api.datacite.org/dois?query=<doi>
      - https://api.datacite.org/dois/<doi>/versions

    Returns:
      {
        "query_doi": ...,
        "current": <normalized latest record>,
        "history": [<normalized version 1>, <normalized version 2>, ...],
        "changes_between_versions": [
            {"from_index": 0, "to_index": 1, "changes": {...}},
            ...
        ]
      }
    """
    if not doi or not doi.strip():
        raise ValueError("DOI must be a non-empty string.")

    doi = doi.strip()

    # 1) Query DOI to get current/best match
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

    # Prefer exact DOI match
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

    # 2) Pull versions endpoint for full metadata iteration history
    #    DataCite supports /dois/{doi}/versions for version history
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
        # Graceful fallback: if versions endpoint unavailable, keep current only
        history = [current]

    # Ensure current exists in history
    current_id = current.get("id")
    if current_id and all(h.get("id") != current_id for h in history):
        history.append(current)

    # Sort by registered/published/updated to approximate chronological order
    def _sort_key(rec: Dict[str, Any]):
        return (
            rec.get("registered") or "",
            rec.get("published") or "",
            rec.get("updated") or "",
            rec.get("id") or "",
        )

    history = sorted(history, key=_sort_key)

    # Build pairwise diffs (detect title/DOI/etc changes across iterations)
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
    # updated/current metadata (exact shape you requested)
    "id": current.get("id"),
    "doi": current.get("doi"),
    "titles": current.get("titles"),
    "creators": current.get("creators"),
    "publisher": current.get("publisher"),
    "publication_year": current.get("publication_year"),
    "resource_type_general": current.get("resource_type_general"),
    "subjects": current.get("subjects"),
    "descriptions": current.get("descriptions"),
    "url": current.get("url"),
    "published": current.get("published"),
    "updated": current.get("updated"),
    "registered": current.get("registered"),
    "language": current.get("language"),
    "rights": current.get("rights"),
    "version": current.get("version"),
    "state": current.get("state"),
    "raw": current.get("raw"),

    # plus all metadata iterations + diff tracking
    "all_versions": history,
    "changes_between_versions": changes_between_versions,
}


if __name__ == "__main__":
    test_doi = "10.5281/zenodo.3727209"

    try:
        result = fetch_datacite_metadata_with_history(test_doi)
        print("Query DOI:", result["query_doi"])
        print("Canonical DOI:", result["canonical_doi"])
        print("Current title:", (result["current"]["titles"] or [None])[0])
        print("Versions found:", len(result["history"]))

        if result["changes_between_versions"]:
            print("\nDetected metadata changes across versions:")
            for ch in result["changes_between_versions"]:
                print(f"- {ch['from_id']} -> {ch['to_id']}")
                for k, v in ch["changes"].items():
                    print(f"    {k}: {v['old']}  =>  {v['new']}")
        else:
            print("\nNo metadata changes detected across versions.")
    except Exception as e:
        print(f"Error: {e}")
