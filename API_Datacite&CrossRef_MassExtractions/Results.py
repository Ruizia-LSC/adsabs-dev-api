import json
from typing import Any, Dict, List

import DataciteDOISearchinCrossref as doi_search
import DataciteTitleSearchinCrossref as title_search


def _run_main(module: Any) -> None:
    """
    Run module.main() if available.
    """
    main_fn = getattr(module, "main", None)
    if callable(main_fn):
        main_fn()


def _load_json_list(path: str) -> List[Dict[str, Any]]:
    """
    Load JSON list from file path. Return [] if file missing/invalid/non-list.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def build_combined_results() -> Dict[str, Any]:
    # Run DOI search script, then read its output file
    _run_main(doi_search)
    doi_output_file = getattr(doi_search, "OUTPUT_FILE", "crossref_datacite_doi_matches.json")
    doi_matches = _load_json_list(doi_output_file)

    # Run Title search script, then read its output file
    _run_main(title_search)
    title_output_file = getattr(
        title_search,
        "OUTPUT_FILE_TITLES",
        "crossref_datacite_title_matches.json",
    )
    title_matches = _load_json_list(title_output_file)

    return {
        "sourceScripts": {
            "doi": "DataciteDOISearchinCrossref.py",
            "title": "DataciteTitleSearchinCrossref.py",
        },
        "sourceFiles": {
            "doiMatchesFile": doi_output_file,
            "titleMatchesFile": title_output_file,
        },
        "counts": {
            "doiMatches": len(doi_matches),
            "titleMatches": len(title_matches),
            "totalMatches": len(doi_matches) + len(title_matches),
        },
        "doiMatches": doi_matches,
        "titleMatches": title_matches,
    }


if __name__ == "__main__":
    result = build_combined_results()
    print(json.dumps(result, indent=2, ensure_ascii=False))
