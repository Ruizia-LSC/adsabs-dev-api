"""
Results.py
----------
For each DataciteResult JSON file, run three checks against every individual
Crossref-call JSON file found in the 10.26093_cds_vizier.1350 folder.

Checks (per Crossref file):
  1. DOITest       – Is the canonical_doi found anywhere in the Crossref JSON?
  2. TitleTest     – Is any current title found anywhere in the Crossref JSON?
     PreviousTitle – Were titles ever different across DataCite history entries?
  3. UnstructuredTest – Does any reference entry contain an "unstructured" field?

One output file is written per DataciteResult, saved to
  API_Datacite&CrossRef_MassExtractions/CrossCheckResults/
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
DATACITE_DIR = SCRIPT_DIR / "DataciteResults"
CROSSREF_DIR = SCRIPT_DIR / "10.26093_cds_vizier.1350"
OUTPUT_DIR = SCRIPT_DIR / "CrossCheckResults"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Optional[Any]:
    """Load a JSON file; return None on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def json_contains_string(obj: Any, needle: str) -> bool:
    """
    Recursively walk *obj* and return True if *needle* (case-insensitive)
    appears in any string value.
    """
    needle_lower = needle.lower()
    if isinstance(obj, str):
        return needle_lower in obj.lower()
    if isinstance(obj, dict):
        return any(json_contains_string(v, needle) for v in obj.values())
    if isinstance(obj, list):
        return any(json_contains_string(item, needle) for item in obj)
    return False


def find_matching_value(obj: Any, needle: str) -> Optional[str]:
    """
    Return the first string value in *obj* that contains *needle*
    (case-insensitive), or None if not found.
    """
    needle_lower = needle.lower()
    if isinstance(obj, str):
        return obj if needle_lower in obj.lower() else None
    if isinstance(obj, dict):
        for v in obj.values():
            result = find_matching_value(v, needle)
            if result is not None:
                return result
    if isinstance(obj, list):
        for item in obj:
            result = find_matching_value(item, needle)
            if result is not None:
                return result
    return None


def collect_unstructured(references: Any) -> List[str]:
    """
    Walk the references list and collect every "unstructured" field value.
    """
    found: List[str] = []
    if not isinstance(references, list):
        return found
    for ref in references:
        if isinstance(ref, dict) and "unstructured" in ref:
            val = ref["unstructured"]
            if isinstance(val, str) and val.strip():
                found.append(val)
    return found


# ---------------------------------------------------------------------------
# Per-file checks
# ---------------------------------------------------------------------------

def check_doi(crossref_data: Any, canonical_doi: str) -> Dict[str, Any]:
    """Check 1: DOI presence."""
    found = json_contains_string(crossref_data, canonical_doi)
    value = find_matching_value(crossref_data, canonical_doi) if found else ""
    return {"DOITest": found, "DOIValue": value}


def check_title(crossref_data: Any, titles: List[str]) -> Dict[str, Any]:
    """Check 2: Title presence (any title in the list)."""
    for title in titles:
        if title and json_contains_string(crossref_data, title):
            value = find_matching_value(crossref_data, title)
            return {"TitleTest": True, "TitleValue": value or ""}
    return {"TitleTest": False, "TitleValue": ""}


def check_previous_title(history: List[Dict[str, Any]]) -> bool:
    """
    Return True if there were ever different titles across history entries.
    Compares each history entry's titles list to the first entry.
    """
    if len(history) < 2:
        return False
    first_titles = set(history[0].get("titles", []))
    for entry in history[1:]:
        if set(entry.get("titles", [])) != first_titles:
            return True
    return False


def check_unstructured(crossref_data: Any) -> Dict[str, Any]:
    """Check 3: Unstructured references."""
    message = crossref_data.get("message", {}) if isinstance(crossref_data, dict) else {}
    references = message.get("reference", [])
    unstructured_texts = collect_unstructured(references)
    if unstructured_texts:
        return {
            "UnstructuredTest": True,
            "UnstructuredText": unstructured_texts,
        }
    return {"UnstructuredTest": False, "UnstructuredText": ""}


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_datacite_file(
    datacite_path: Path,
    crossref_files: List[Path],
) -> Dict[str, Any]:
    """
    Run all checks for one DataciteResult file against all Crossref files.
    Returns the combined output dict.
    """
    datacite_data = load_json(datacite_path)
    if datacite_data is None:
        return {"error": f"Could not load {datacite_path.name}"}

    canonical_doi: str = datacite_data.get("canonical_doi", "")
    current: Dict[str, Any] = datacite_data.get("current", {})
    history: List[Dict[str, Any]] = datacite_data.get("history", [])
    current_titles: List[str] = current.get("titles", [])

    previous_title_flag = check_previous_title(history)

    results: List[Dict[str, Any]] = []

    for cf_path in sorted(crossref_files):
        crossref_data = load_json(cf_path)
        if crossref_data is None:
            continue

        # Derive the publication DOI from the file itself (stored as original_doi)
        original_doi: str = (
            crossref_data.get("original_doi", "")
            if isinstance(crossref_data, dict)
            else ""
        )
        if not original_doi:
            original_doi = cf_path.stem.replace("_CrossrefCall", "").replace("_", "/")

        doi_check = check_doi(crossref_data, canonical_doi)
        title_check = check_title(crossref_data, current_titles)
        unstructured_check = check_unstructured(crossref_data)

        entry: Dict[str, Any] = {
            "Publication DOI": original_doi,
            "DOITest": doi_check["DOITest"],
            "DOIValue": doi_check["DOIValue"],
            "TitleTest": title_check["TitleTest"],
            "TitleValue": title_check["TitleValue"],
            "PreviousTitle": previous_title_flag,
            "UnstructuredTest": unstructured_check["UnstructuredTest"],
            "UnstructuredText": unstructured_check["UnstructuredText"],
        }
        results.append(entry)

    output: Dict[str, Any] = {
        "datasetDOI": canonical_doi,
        "datasetTitle": current_titles,
        "results": results,
    }
    return output


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all Crossref call files once
    crossref_files: List[Path] = sorted(
        p for p in CROSSREF_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    )
    if not crossref_files:
        print(f"No Crossref files found in {CROSSREF_DIR}")
        return

    # Collect all DataciteResult files
    datacite_files: List[Path] = sorted(
        p for p in DATACITE_DIR.iterdir()
        if p.is_file() and p.suffix.upper() == ".JSON"
    )
    if not datacite_files:
        print(f"No DataciteResult files found in {DATACITE_DIR}")
        return

    print(
        f"Processing {len(datacite_files)} DataciteResult file(s) "
        f"against {len(crossref_files)} Crossref file(s)."
    )

    for dc_path in datacite_files:
        output = process_datacite_file(dc_path, crossref_files)

        # Name the output file after the DataciteResult file
        stem = dc_path.stem  # e.g. "10.26093_cds_vizier.1350_DataciteResult"
        out_name = stem.replace("_DataciteResult", "_CrossCheckResult") + ".json"
        out_path = OUTPUT_DIR / out_name

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2, ensure_ascii=False)

        total = len(output.get("results", []))
        doi_hits = sum(1 for r in output.get("results", []) if r.get("DOITest"))
        title_hits = sum(1 for r in output.get("results", []) if r.get("TitleTest"))
        unstr_hits = sum(1 for r in output.get("results", []) if r.get("UnstructuredTest"))

        print(
            f"  {dc_path.name} → {out_name} "
            f"({total} publications checked | "
            f"DOI hits: {doi_hits}, Title hits: {title_hits}, "
            f"Unstructured hits: {unstr_hits})"
        )

    print(f"\nDone. Results written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
