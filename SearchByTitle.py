import json
import time
import requests
from pathlib import Path
from urllib.parse import quote

INPUT_FILE = "cited_list.json"
CROSSREF_BASE = "https://api.crossref.org/works/"


def load_records(file_path: str) -> list[dict]:
    """
    Load records containing title + citation_doi.

    Supported input shapes:
      - [{"title": "...", "citation_doi": "..."}]
      - {"records": [{"title": "...", "citation_doi": "..."}]}
    """
    data = json.loads(Path(file_path).read_text(encoding="utf-8"))
    records = []

    def extract(items):
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            citation_doi = item.get("citation_doi")
            if title and citation_doi:
                records.append(
                    {
                        "title": str(title).strip(),
                        "citation_doi": str(citation_doi).strip(),
                    }
                )

    if isinstance(data, list):
        extract(data)
    elif isinstance(data, dict):
        if isinstance(data.get("records"), list):
            extract(data["records"])

    seen = set()
    clean = []
    for r in records:
        key = (r["title"].lower(), r["citation_doi"].lower())
        if r["title"] and r["citation_doi"] and key not in seen:
            seen.add(key)
            clean.append(r)

    return clean


def title_in_crossref_metadata(target_title: str, metadata: dict) -> bool:
    """
    Return True if target_title appears in Crossref metadata fields.
    """
    target = target_title.strip().lower()
    if not target:
        return False

    title_list = metadata.get("title", [])
    container_list = metadata.get("container-title", [])
    short_title_list = metadata.get("short-title", [])
    subtitle_list = metadata.get("subtitle", [])

    candidates = []

    for lst in (title_list, container_list, short_title_list, subtitle_list):
        if isinstance(lst, list):
            candidates.extend([str(x) for x in lst if isinstance(x, str)])

    publisher = metadata.get("publisher")
    if isinstance(publisher, str):
        candidates.append(publisher)

    combined = " ".join(candidates).lower()
    return target in combined


def doi_matches_title(citation_doi: str, title: str, session: requests.Session) -> bool:
    """
    Query Crossref by DOI and check if title is present in metadata.
    """
    url = CROSSREF_BASE + quote(citation_doi, safe="")
    headers = {"User-Agent": "doi-title-checker/1.0 (mailto:your-email@example.com)"}

    try:
        resp = session.get(url, headers=headers, timeout=20)
        if resp.status_code == 404:
            return False

        resp.raise_for_status()
        message = resp.json().get("message", {})
        return title_in_crossref_metadata(title, message)

    except (requests.RequestException, ValueError):
        return False


def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError(f"{INPUT_FILE} not found in current directory.")

    records = load_records(INPUT_FILE)
    if not records:
        print("No valid records found. Expected title + citation_doi in cited_list.json")
        return

    matched_dois = []
    with requests.Session() as session:
        for i, rec in enumerate(records, start=1):
            title = rec["title"]
            citation_doi = rec["citation_doi"]

            print(f"[{i}/{len(records)}] Checking DOI: {citation_doi}")
            if doi_matches_title(citation_doi, title, session):
                matched_dois.append(citation_doi)

            time.sleep(0.1)

    for doi in matched_dois:
        print(doi)


if __name__ == "__main__":
    main()
