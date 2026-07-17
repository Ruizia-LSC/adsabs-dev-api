import json
import time
import requests
from pathlib import Path
from urllib.parse import quote


INPUT_FILE = "cited_list.json"
OUTPUT_FILE = "doi_titles.json"
CROSSREF_BASE = "https://api.crossref.org/works/"


def load_dois(file_path: str) -> list[str]:
    """
    Load DOIs from cited_list.json.
    Supports:
      - ["10.xxxx/abc", "10.xxxx/def"]
      - [{"doi": "10.xxxx/abc"}, {"DOI": "10.xxxx/def"}]
      - {"dois": ["10.xxxx/abc", "10.xxxx/def"]}
    """
    data = json.loads(Path(file_path).read_text(encoding="utf-8"))

    dois = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                dois.append(item.strip())
            elif isinstance(item, dict):
                doi = item.get("doi") or item.get("DOI")
                if doi:
                    dois.append(str(doi).strip())

    elif isinstance(data, dict):
        if isinstance(data.get("dois"), list):
            for item in data["dois"]:
                if isinstance(item, str):
                    dois.append(item.strip())
                elif isinstance(item, dict):
                    doi = item.get("doi") or item.get("DOI")
                    if doi:
                        dois.append(str(doi).strip())

    # remove empties + deduplicate while preserving order
    seen = set()
    clean = []
    for d in dois:
        if d and d not in seen:
            seen.add(d)
            clean.append(d)

    return clean


def get_title_from_crossref(doi: str, session: requests.Session) -> dict:
    """
    Query Crossref for a DOI and return title-related data.
    """
    url = CROSSREF_BASE + quote(doi, safe="")
    headers = {
        "User-Agent": "doi-title-fetcher/1.0 (mailto:your-email@example.com)"
    }

    try:
        resp = session.get(url, headers=headers, timeout=20)
        if resp.status_code == 404:
            return {"doi": doi, "status": "not_found", "title": None, "dataset_title": None}

        resp.raise_for_status()
        payload = resp.json().get("message", {})

        # Crossref usually stores title as list
        title_list = payload.get("title", [])
        title = title_list[0] if isinstance(title_list, list) and title_list else None

        # Some records may include container-title or alternative fields
        container_list = payload.get("container-title", [])
        container_title = (
            container_list[0] if isinstance(container_list, list) and container_list else None
        )

        # Identify whether this is dataset-like content
        work_type = payload.get("type")

        return {
            "doi": doi,
            "status": "ok",
            "type": work_type,
            "title": title,
            "container_title": container_title,
            "dataset_title": title if work_type == "dataset" else None,
            "url": payload.get("URL"),
            "publisher": payload.get("publisher"),
            "issued": payload.get("issued"),
        }

    except requests.RequestException as e:
        return {"doi": doi, "status": "error", "error": str(e), "title": None, "dataset_title": None}
    except ValueError as e:
        return {"doi": doi, "status": "error", "error": f"Invalid JSON: {e}", "title": None, "dataset_title": None}


def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError(f"{INPUT_FILE} not found in current directory.")

    dois = load_dois(INPUT_FILE)
    if not dois:
        print("No DOIs found in cited_list.json")
        return

    results = []
    with requests.Session() as session:
        for i, doi in enumerate(dois, start=1):
            print(f"[{i}/{len(dois)}] Fetching: {doi}")
            result = get_title_from_crossref(doi, session)
            results.append(result)
            time.sleep(0.1)  # polite delay for API calls

    Path(OUTPUT_FILE).write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\nDone. Wrote {len(results)} records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
