#Step 1 
import json

# Load the cited_list100.json file
with open("cited_list100.json", "r", encoding="utf-8") as f:
    cited_data = json.load(f)

doi_list = []
for record in cited_data:
    dois = record.get("doi", [])
    if dois:
        doi_list.extend(dois)

print("Extracted DOIs:")
for i, doi in enumerate(doi_list):
    print(f"{i + 1}. {doi}")
#Step2
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
  #Step3
  import json
import time

# Ensure doi_list and fetch_datacite_metadata_with_history are available
if 'doi_list' in locals() and 'fetch_datacite_metadata_with_history' in globals():
    processed_count = 0
    failed_dois = []

    for i, current_doi in enumerate(doi_list):
        print(f"\nProcessing DOI {i + 1}/{len(doi_list)}: {current_doi}")
        try:
            # Fetch metadata for the current DOI
            datacite_result_all = fetch_datacite_metadata_with_history(current_doi)

            # Create a valid filename from the DOI
            filename = f"{current_doi.replace('/', '_')}_DataciteResult.JSON"

            # Save the datacite_result to the JSON file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(datacite_result_all, f, ensure_ascii=False, indent=2)

            print(f"Successfully saved metadata for {current_doi} to {filename}")
            processed_count += 1

        except Exception as e:
            print(f"Failed to fetch or save metadata for {current_doi}: {e}")
            failed_dois.append(current_doi)

        # Add a small delay to avoid hitting API rate limits, if applicable
        time.sleep(0.5)

    print(f"\nFinished processing. Total DOIs processed: {processed_count}/{len(doi_list)}")
    if failed_dois:
        print("DOIs that failed to process:")
        for failed_doi in failed_dois:
            print(f"- {failed_doi}")
else:
    print("Error: 'doi_list' or 'fetch_datacite_metadata_with_history' not found. Please ensure preceding cells were executed.")
  
#Step4 for download 

  import zipfile
import glob
from google.colab import files

# Find all generated JSON files
json_files = glob.glob('*_DataciteResult.JSON')

if json_files:
    zip_filename = 'DataciteResults.zip'
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for file in json_files:
            zipf.write(file)
    print(f'Successfully created {zip_filename} containing {len(json_files)} JSON files.')

    # Offer the zip file for download
    files.download(zip_filename)
else:
    print('No DataCiteResult.JSON files found to zip.')
