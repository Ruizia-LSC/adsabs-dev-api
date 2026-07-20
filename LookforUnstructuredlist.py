import json
import time
from pathlib import Path

import requests


def get_unstructured_citations_for_doi(doi: str, timeout: int = 30) -> list[str]:
    """Return 'unstructured' reference entries from Crossref /works for a DOI."""
    url = f"https://api.crossref.org/works/{doi}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    message = response.json().get("message", {})
    references = message.get("reference", [])

    return [
        ref["unstructured"]
        for ref in references
        if isinstance(ref, dict) and "unstructured" in ref and ref["unstructured"]
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


def run_unstructured_search_for_citation_dois(
    json_path: str,
    output_path: str = "unstructured_citation_doi_results.json",
    timeout: int = 30,
    sleep_seconds: float = 0.2,
) -> dict:
    """
    For each DOI in citation_doi from cited_list100.json:
      - query Crossref /works/{doi}
      - collect unstructured references
    Save full results to output_path.
    """
    dois = load_citation_dois(json_path)
    total = len(dois)

    results: dict[str, dict] = {}

    for idx, doi in enumerate(dois, start=1):
        print(f"[{idx}/{total}] Processing citation DOI: {doi}")
        try:
            unstructured = get_unstructured_citations_for_doi(doi, timeout=timeout)
            results[doi] = {
                "status": "ok",
                "unstructured_count": len(unstructured),
                "unstructured": unstructured,
            }
        except requests.HTTPError as e:
            results[doi] = {
                "status": "http_error",
                "error": str(e),
                "unstructured_count": 0,
                "unstructured": [],
            }
        except requests.RequestException as e:
            results[doi] = {
                "status": "request_error",
                "error": str(e),
                "unstructured_count": 0,
                "unstructured": [],
            }
        except Exception as e:
            results[doi] = {
                "status": "error",
                "error": str(e),
                "unstructured_count": 0,
                "unstructured": [],
            }

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    summary = {
        "input_file": str(json_path),
        "source_field": "citation_doi",
        "total_citation_dois": total,
        "processed": len(results),
        "ok": sum(1 for v in results.values() if v["status"] == "ok"),
        "with_unstructured": sum(
            1
            for v in results.values()
            if v["status"] == "ok" and v["unstructured_count"] > 0
        ),
        "errors": sum(1 for v in results.values() if v["status"] != "ok"),
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
    output_json = Path("unstructured_citation_doi_results.json")

    if not input_json.exists():
        raise FileNotFoundError(f"Input file not found: {input_json}")

    payload = run_unstructured_search_for_citation_dois(
        json_path=str(input_json),
        output_path=str(output_json),
        timeout=30,
        sleep_seconds=0.2,
    )

    print("\nDone.")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Saved detailed results to: {output_json}")
