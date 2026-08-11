"""
Results.py
----------
Runs checks for ONE DataciteResult JSON file against every individual
Crossref-call JSON file found in the corresponding sibling Crossref folder.

Pair example
  DataciteResult file : 10.7927_NQ55-CR83_DataciteResult.JSON
  Crossref folder     : 10.7927_NQ55-CR83/

The sibling relationship is derived automatically from the DataciteResult
filename: strip the "_DataciteResult" suffix to get the Crossref folder name.

Checks (per Crossref file):
  1. DOITest        – Is the canonical_doi found anywhere in the Crossref JSON?
  2. TitleTest      – Is any current title found anywhere in the Crossref JSON?
     PreviousTitle  – Were titles ever different across DataCite history entries?
  3. ContainerFound – Container(s) where DOI/title metadata are found;
     "null" if both DOITest and TitleTest are False, or if canonical_doi is blank,
     or if titles are empty/blank.

Output is written to
  cited_list10_0_MassExtractions/CrossCheckResults/

GitHub API pagination
---------------------
When running against a GitHub repository via the API, directories with many
files (300+) require paginated requests.  Set the environment variables
  GITHUB_TOKEN  – a personal-access token (needed for private repos or higher
                  rate limits; optional for public repos)
  GITHUB_OWNER  – repository owner / organisation (e.g. "Ruizia-LSC")
  GITHUB_REPO   – repository name (e.g. "adsabs-dev-api")
  GITHUB_REF    – git ref to read from (branch / tag / SHA; default "main")
and the script will fetch all JSON files via the GitHub Contents API with
full pagination support instead of reading from the local filesystem.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# GitHub API helpers (pagination)
# ---------------------------------------------------------------------------

_GITHUB_API = "https://api.github.com"


def _github_token() -> Optional[str]:
    """Return the GitHub token from the environment, or None."""
    return os.environ.get("GITHUB_TOKEN")


def _github_request(url: str) -> Any:
    """
    Perform a single authenticated GET request to *url* and return the parsed
    JSON body.  Raises ``urllib.error.URLError`` / ``urllib.error.HTTPError``
    on failure.
    """
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    token = _github_token()
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def list_github_json_files(
    owner: str,
    repo: str,
    path: str,
    ref: str = "main",
) -> List[str]:
    """
    Return the download URLs of all JSON files found at *path* in the given
    GitHub repository, handling API pagination automatically.

    The GitHub Contents API returns at most 1 000 entries per page when
    accessed via the ``?per_page=100`` parameter (the actual cap is 1 000
    items but using 100-item pages keeps the responses manageable).

    Parameters
    ----------
    owner : str
        Repository owner / organisation.
    repo : str
        Repository name.
    path : str
        Directory path inside the repository (e.g. "cited_list10_0_MassExtractions/10.5066_F7P55KJN").
    ref : str
        Git ref (branch, tag, or commit SHA) to read from.

    Returns
    -------
    list of str
        Sorted list of raw-content download URLs for every ``.json`` file in
        the directory.
    """
    download_urls: List[str] = []
    page = 1
    per_page = 100  # GitHub max per page for Contents API

    while True:
        url = (
            f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
            f"?ref={ref}&per_page={per_page}&page={page}"
        )
        try:
            entries = _github_request(url)
        except urllib.error.HTTPError as exc:
            print(f"WARNING: GitHub API error for {url}: {exc}")
            break
        except urllib.error.URLError as exc:
            print(f"WARNING: Network error for {url}: {exc}")
            break

        if not isinstance(entries, list):
            # Might be a single-file response or an error dict
            break

        json_entries = [
            e["download_url"]
            for e in entries
            if isinstance(e, dict)
            and e.get("type") == "file"
            and e.get("name", "").lower().endswith(".json")
            and e.get("download_url")
        ]
        download_urls.extend(json_entries)

        # Stop when the API returns an empty page or fewer entries than
        # requested (last page).  We check *both* conditions so that a full
        # page of non-JSON entries does not cause an infinite loop.
        if not entries or len(entries) < per_page:
            break
        page += 1

    return sorted(download_urls)


def load_json_from_url(url: str) -> Optional[Any]:
    """Download a JSON file from *url* and return the parsed content."""
    try:
        req = urllib.request.Request(url)
        token = _github_token()
        if token:
            req.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: Could not fetch {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent

# Pass dataset base via CLI, e.g.:
#   python Resuts.py 10.5066_F7P55KJN
# Defaults to previous dataset if omitted.
DATASET_BASE = sys.argv[1] if len(sys.argv) > 1 else "10.7927_NQ55-CR83"

# Single DataciteResult file to process
DATACITE_FILE: Path = SCRIPT_DIR / f"{DATASET_BASE}_DataciteResult.JSON"

# Sibling Crossref folder derived from dataset base.
# e.g. "10.5066_F7P55KJN" -> "10.5066_F7P55KJN/"
CROSSREF_DIR: Path = SCRIPT_DIR / DATASET_BASE

# Output folder
OUTPUT_DIR: Path = SCRIPT_DIR / "CrossCheckResults"


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
      - one raw container (dict or list) if DOI and title resolve to the same container
      - list of raw containers if they resolve to different containers
    """
    if not canonical_doi or not canonical_doi.strip():
        return "null"
    if not titles or not any(isinstance(t, str) and t.strip() for t in titles):
        return "null"
    if not doi_found and not title_found:
        return "null"

    containers: List[Any] = []
    seen: set = set()

    if doi_found:
        doi_container = find_container(crossref_data, canonical_doi)
        if doi_container is not None:
            norm = _normalize_container(doi_container)
            if norm not in seen:
                seen.add(norm)
                containers.append(doi_container)

    if title_found:
        for title in titles:
            if title and json_contains_string(crossref_data, title):
                title_container = find_container(crossref_data, title)
                if title_container is not None:
                    norm = _normalize_container(title_container)
                    if norm not in seen:
                        seen.add(norm)
                        containers.append(title_container)
                break

    if not containers:
        return "null"
    if len(containers) == 1:
        return containers[0]
    return containers


# ---------------------------------------------------------------------------
# Core processing
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
    total = len(crossref_files)

    for idx, cf_path in enumerate(sorted(crossref_files), start=1):
        if idx % 100 == 0 or idx == total:
            print(f"  Processing file {idx}/{total} …", flush=True)

        crossref_data = load_json(cf_path)
        if crossref_data is None:
            continue

        # Derive the publication DOI from the file itself (stored as original_doi),
        # or fall back to reconstructing it from the filename.
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

        results.append({
            "Publication DOI": original_doi,
            "DOITest": doi_check["DOITest"],
            "TitleTest": title_check["TitleTest"],
            "PreviousTitle": previous_title_flag,
            "ContainerFound": container_found,
        })

    return {
        "datasetDOI": canonical_doi,
        "datasetTitle": current_titles,
        "results": results,
    }


def _process_via_urls(
    datacite_path: Path,
    download_urls: List[str],
) -> Dict[str, Any]:
    """
    Like :func:`process_datacite_file` but loads Crossref data from remote
    download URLs (GitHub raw content) instead of local ``Path`` objects.
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
    total = len(download_urls)

    for idx, url in enumerate(download_urls, start=1):
        if idx % 100 == 0 or idx == total:
            print(f"  Processing file {idx}/{total} …", flush=True)

        crossref_data = load_json_from_url(url)
        if crossref_data is None:
            continue

        original_doi: str = (
            crossref_data.get("original_doi", "")
            if isinstance(crossref_data, dict)
            else ""
        )
        if not original_doi:
            # Derive from the last path segment of the URL
            filename = url.rstrip("/").split("/")[-1]
            stem = filename[: filename.rfind(".")] if "." in filename else filename
            original_doi = stem.replace("_CrossrefCall", "").replace("_", "/")

        doi_check = check_doi(crossref_data, canonical_doi)
        title_check = check_title(crossref_data, current_titles)
        container_found = check_container_found(
            crossref_data,
            canonical_doi,
            current_titles,
            doi_check["DOITest"],
            title_check["TitleTest"],
        )

        results.append({
            "Publication DOI": original_doi,
            "DOITest": doi_check["DOITest"],
            "TitleTest": title_check["TitleTest"],
            "PreviousTitle": previous_title_flag,
            "ContainerFound": container_found,
        })

    return {
        "datasetDOI": canonical_doi,
        "datasetTitle": current_titles,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Validate inputs before doing anything
    if not DATACITE_FILE.is_file():
        print(f"ERROR: DataciteResult file not found:\n  {DATACITE_FILE}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Determine whether to use local filesystem or GitHub API
    # ------------------------------------------------------------------
    gh_owner = os.environ.get("GITHUB_OWNER", "").strip()
    gh_repo = os.environ.get("GITHUB_REPO", "").strip()
    gh_ref = os.environ.get("GITHUB_REF", "main").strip()

    use_github_api = bool(gh_owner and gh_repo)

    if use_github_api:
        # Allow an explicit override via GITHUB_PATH env var.
        gh_path_override = os.environ.get("GITHUB_PATH", "").strip()
        if gh_path_override:
            github_path = gh_path_override
        else:
            # Derive the repository-relative path from the local filesystem:
            # resolve CROSSREF_DIR relative to the current working directory
            # (assumed to be the repository root when running in CI).
            try:
                repo_relative = CROSSREF_DIR.resolve().relative_to(Path.cwd().resolve())
                github_path = repo_relative.as_posix()
            except ValueError:
                print(
                    "ERROR: Cannot determine the repository-relative path for the "
                    "Crossref folder.\n"
                    "  Set the GITHUB_PATH environment variable to the path of the "
                    "Crossref folder inside the repository.\n"
                    f"  Example: export GITHUB_PATH=\"cited_list10_0_MassExtractions/{CROSSREF_DIR.name}\""
                )
                return

        print(
            f"Mode           : GitHub API  (owner={gh_owner} repo={gh_repo} ref={gh_ref})\n"
            f"DataciteResult : {DATACITE_FILE.name}\n"
            f"Crossref path  : {github_path}  (fetching file list…)"
        )

        download_urls = list_github_json_files(gh_owner, gh_repo, github_path, gh_ref)

        if not download_urls:
            print(f"No Crossref JSON files found via GitHub API at: {github_path}")
            return

        total_files = len(download_urls)
        print(f"Crossref files : {total_files} file(s) found\n")

        # Process using URL-based loading
        output = _process_via_urls(DATACITE_FILE, download_urls)

    else:
        # Local filesystem mode
        if not CROSSREF_DIR.is_dir():
            print(f"ERROR: Sibling Crossref folder not found:\n  {CROSSREF_DIR}")
            return

        crossref_files: List[Path] = sorted(
            p for p in CROSSREF_DIR.iterdir()
            if p.is_file() and p.suffix.lower() == ".json"
        )
        if not crossref_files:
            print(f"No Crossref JSON files found in {CROSSREF_DIR}")
            return

        total_files = len(crossref_files)
        print(
            f"Mode           : local filesystem\n"
            f"DataciteResult : {DATACITE_FILE.name}\n"
            f"Crossref folder: {CROSSREF_DIR.name}/  ({total_files} file(s))\n"
        )

        output = process_datacite_file(DATACITE_FILE, crossref_files)

    # Name the output after the DataciteResult stem
    # e.g. "10.7927_NQ55-CR83_DataciteResult" -> "10.7927_NQ55-CR83_CrossCheckResult.json"
    out_name = DATACITE_FILE.stem.replace("_DataciteResult", "_CrossCheckResult") + ".json"
    out_path = OUTPUT_DIR / out_name

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    total = len(output.get("results", []))
    doi_hits = sum(1 for r in output.get("results", []) if r.get("DOITest"))
    title_hits = sum(1 for r in output.get("results", []) if r.get("TitleTest"))

    print(
        f"Output : {out_path}\n"
        f"Summary: {total} publications checked | "
        f"DOI hits: {doi_hits} | Title hits: {title_hits}"
    )


if __name__ == "__main__":
    main()
