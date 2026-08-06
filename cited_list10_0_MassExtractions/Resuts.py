"""
Results.py
----------
For each DataciteResult JSON file, run checks against every individual
Crossref-call JSON file found in the corresponding Datacite folder.

Checks (per Crossref file):
  1. DOITest       – Is the canonical_doi found anywhere in the Crossref JSON?
  2. TitleTest     – Is any current title found anywhere in the Crossref JSON?
     PreviousTitle – Were titles ever different across DataCite history entries?
  3. ContainerFound – Container(s) where DOI/title metadata are found;
     "null" if both DOITest and TitleTest are False, or if canonical_doi is blank,
     or if titles are empty/blank.

One output file is written per DataciteResult, saved to
  API_Datacite&CrossRef_MassExtractions/CrossCheckResults/
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
DATACITE_DIR = SCRIPT_DIR / "10.7927_NQ55-CR83_DataciteResult.JSON"
CROSSREF_DIR = SCRIPT_DIR / "10.7927_NQ55-CR83"
OUTPUT_DIR = SCRIPT_DIR / "CrossCheckResults10.7927_NQ55-CR83"


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


def _normalize_container(value: Any) -> str:
    """Normalize container representation so equivalent containers de-duplicate."""
    if isinstance(value, dict):
        try:
            return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2)
        except TypeError:
            return str(value)
    if isinstance(value, list):
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except TypeError:
            return str(value)
    return str(value)


def find_container(obj: Any, needle: str) -> Optional[Any]:
    """
    Return the nearest container (dict or list) holding a string that contains
    *needle* (case-insensitive). Returns None if not found.
    """
    needle_lower = needle.lower()

    def _walk(node: Any, parent: Optional[Any]) -> Optional[Any]:
        if isinstance(node, str):
            if needle_lower in node.lower():
                return parent
            return None
        if isinstance(node, dict):
            for v in node.values():
                found = _walk(v, node)
                if found is not None:
                    return found
            return None
        if isinstance(node, list):
            for item in node:
                found = _walk(item, node)
                if found is not None:
                    return found
            return None
        return None

    return _walk(obj, None)


# ---------------------------------------------------------------------------
# Per-file checks
# ---------------------------------------------------------------------------

def check_doi(crossref_data: Any, canonical_doi: str) -> Dict[str, Any]:
    """Check 1: DOI presence."""
    found = json_contains_string(crossref_data, canonical_doi)
    return {"DOITest": found}


def check_title(crossref_data: Any, titles: List[str]) -> Dict[str, Any]:
    """Check 2: Title presence (any title in the list)."""
    for title in titles:
        if title and json_contains_string(crossref_data, title):
            return {"TitleTest": True}
    return {"TitleTest": False}


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


def check_container_found(
    crossref_data: Any,
    canonical_doi: str,
    titles: List[str],
    doi_found: bool,
    title_found: bool,
) -> Any:
    """
    Return:
      - "null" if both tests are False
      - "null" if canonical_doi is blank
      - "null" if titles are empty/blank
      - one raw container (dict or list) if DOI and title resolve to same container
      - list of raw containers if they resolve to different containers
    """
    # Validation guard: if canonical DOI is blank OR titles are empty/blank,
    # force ContainerFound to "null".
    if not canonical_doi or not canonical_doi.strip():
        return "null"
    if not titles or not any(isinstance(t, str) and t.strip() for t in titles):
        return "null"

    if not doi_found and not title_found:
        return "null"

    containers: List[Any] = []  # store raw dicts/lists for proper pretty-printing
    seen = set()

    if doi_found:
        doi_container = find_container(crossref_data, canonical_doi)
        if doi_container is not None:
            norm = _normalize_container(doi_container)  # used only for dedup
            if norm not in seen:
                seen.add(norm)
                containers.append(doi_container)  # append raw object

    if title_found:
        title_container_raw = None
        for title in titles:
            if title and json_contains_string(crossref_data, title):
                title_container_raw = find_container(crossref_data, title)
                break
        if title_container_raw is not None:
            norm = _normalize_container(title_container_raw)
            if norm not in seen:
                seen.add(norm)
                containers.append(title_container_raw)  # append raw object

    if not containers:
        return "null"
    if len(containers) == 1:
        return containers[0]
    return containers


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
        container_found = check_container_found(
            crossref_data,
            canonical_doi,
            current_titles,
            doi_check["DOITest"],
            title_check["TitleTest"],
        )

        entry: Dict[str, Any] = {
            "Publication DOI": original_doi,
            "DOITest": doi_check["DOITest"],
            "TitleTest": title_check["TitleTest"],
            "PreviousTitle": previous_title_flag,
            "ContainerFound": container_found,  # raw object; json.dump handles formatting
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

        print(
            f"  {dc_path.name} → {out_name} "
            f"({total} publications checked | "
            f"DOI hits: {doi_hits}, Title hits: {title_hits})"
        )

    print(f"\nDone. Results written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
