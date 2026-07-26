import json
import time
from pathlib import Path

import requests


def get_dataset_datacitations_for_doi(doi: str, timeout: int = 30) -> list[dict]:
    """Return entries where 'type' is 'dataset' from Crossref beta/datacitations for a DOI."""
    url = f"https://api.crossref.org/beta/datacitations/{doi}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    message = response.json().get("message", {})
    items = message.get("items", [])

    return [
        item
        for item in items
        if isinstance(item, dict) and item.get("type") == "dataset"
    ]


def load_citation_dois(json_path: str) -> list[str]:
    """
    Load citation DOIs from cited_list100.json.
    Each top-level record may include "citation_doi": [ ... ].
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dois: list[str] = []
    for item in data:
        item_dois = item.get("citation_doi", [])
        if isinstance(item_dois, list):
            for d in item_dois:
                if isinstance(d, str) and d.strip():
                    dois.append(d.strip())

    # Deduplicate while preserving order
    return list(dict.fromkeys(dois))


def run_dataset_datacitation_search_for_citation_dois(
    json_path: str,
    output_path: str = "datacitation_dataset_results.json",
    timeout: int = 30,
    sleep_seconds: float = 0.2,
) -> dict:
    """
    For each DOI in citation_doi from cited_list100.json:
      - query Crossref beta/datacitations/{doi}
      - collect entries where type is 'dataset'
    Save full results to output_path.
    Also list exactly which DOIs fall into with_datasets, no_datasets, and errors.
    Print all dataset datacitations found for each DOI.
    """
    dois = load_citation_dois(json_path)
    total = len(dois)

    results: dict[str, dict] = {}
    with_datasets_dois: list[str] = []
    no_datasets_dois: list[str] = []
    error_dois: list[str] = []

    for idx, doi in enumerate(dois, start=1):
        print(f"[{idx}/{total}] Processing citation DOI: {doi}")
        try:
            datasets = get_dataset_datacitations_for_doi(doi, timeout=timeout)
            has_datasets = len(datasets) > 0
            results[doi] = {
                "status": "ok",
                "category": "with_datasets" if has_datasets else "no_datasets",
                "dataset_count": len(datasets),
                "datasets": datasets,
            }
            if has_datasets:
                with_datasets_dois.append(doi)
                print(f"  Found {len(datasets)} dataset datacitation(s):")
                for dataset_idx, dataset in enumerate(datasets, start=1):
                    print(f"    {dataset_idx}. {dataset}")
            else:
                no_datasets_dois.append(doi)
                print("  No dataset datacitations found.")
        except requests.HTTPError as e:
            results[doi] = {
                "status": "http_error",
                "category": "errors",
                "error": str(e),
                "dataset_count": 0,
                "datasets": [],
            }
            error_dois.append(doi)
            print(f"  HTTP error: {e}")
        except requests.RequestException as e:
            results[doi] = {
                "status": "request_error",
                "category": "errors",
                "error": str(e),
                "dataset_count": 0,
                "datasets": [],
            }
            error_dois.append(doi)
            print(f"  Request error: {e}")
        except Exception as e:
            results[doi] = {
                "status": "error",
                "category": "errors",
                "error": str(e),
                "dataset_count": 0,
                "datasets": [],
            }
            error_dois.append(doi)
            print(f"  Unexpected error: {e}")

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    summary = {
        "input_file": str(json_path),
        "source_field": "citation_doi",
        "total_citation_dois": total,
        "processed": len(results),
        "ok": sum(1 for v in results.values() if v["status"] == "ok"),
        "with_datasets": len(with_datasets_dois),
        "no_datasets": len(no_datasets_dois),
        "errors": len(error_dois),
        "doi_lists": {
            "with_datasets": with_datasets_dois,
            "no_datasets": no_datasets_dois,
            "errors": error_dois,
        },
    }

    payload = {
        "summary": summary,
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return payload


if __name__ == "__main__":
    input_json = Path("cited_list100.json")
    output_json = Path("datacitation_dataset_results.json")

    if not input_json.exists():
        raise FileNotFoundError(f"Input file not found: {input_json}")

    payload = run_dataset_datacitation_search_for_citation_dois(
        json_path=str(input_json),
        output_path=str(output_json),
        timeout=30,
        sleep_seconds=0.2,
    )

    print("\nDone.")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Saved detailed results to: {output_json}")
