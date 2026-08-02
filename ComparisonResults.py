import json
from typing import Any, Dict, List


def build_publication_result(
    doi: str,
    title_test: bool,
    title_value: str,
    previous_title: bool,
    doi_test: bool,
    doi_value: str,
    unstructured_test: bool,
    source_container: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build one PublicationDOI entry from predefined checks.
    """
    return {
        "doi": doi,
        "titleTest": title_test,
        "titleValue": title_value,
        "previousTitle": previous_title,
        "DOITest": doi_test,
        "DOIValue": doi_value,
        "unstructuredTest": unstructured_test,
        "sourceContainer": source_container,
    }


def build_comparison_results(
    dataset_doi: str,
    dataset_title: str,
    publication_checks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the top-level comparison result payload.
    publication_checks should contain precomputed boolean/value checks.
    """
    publication_results = []
    for check in publication_checks:
        publication_results.append(
            build_publication_result(
                doi=check.get("doi", ""),
                title_test=check.get("titleTest", False),
                title_value=check.get("titleValue", ""),
                previous_title=check.get("previousTitle", False),
                doi_test=check.get("DOITest", False),
                doi_value=check.get("DOIValue", ""),
                unstructured_test=check.get("unstructuredTest", False),
                source_container=check.get("sourceContainer", {}),
            )
        )

    return {
        "datasetDOI": dataset_doi,
        "datasetTitle": dataset_title,
        "PublicationDOI": publication_results,
    }


if __name__ == "__main__":
    # Example: predefined checks (replace with your real matching logic output)
    predefined_checks = [
        {
            "doi": "publication doi here",
            "titleTest": True,
            "titleValue": "title text found in the Crossref API",
            "previousTitle": False,
            "DOITest": True,
            "DOIValue": "DOI value found associated with the title",
            "unstructuredTest": True,
            "sourceContainer": {
                "source": "Crossref",
                "matchedBy": ["title", "doi", "unstructured"],
            },
        },
        {
            "doi": "publication doi here",
            "titleTest": True,
            "titleValue": "title text found in the crossref API",
            "previousTitle": True,
            "DOITest": False,
            "DOIValue": "DOI value found associated with the title",
            "unstructuredTest": True,
            "sourceContainer": {
                "source": "Crossref",
                "matchedBy": ["title", "unstructured"],
            },
        },
    ]

    result = build_comparison_results(
        dataset_doi="",
        dataset_title="example title",
        publication_checks=predefined_checks,
    )

    print(json.dumps(result, indent=2))
