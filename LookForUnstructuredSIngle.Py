#Pulls "Unstructured" citations from a single DOI API call
import requests


def get_unstructured_citations_for_doi(doi: str, timeout: int = 30) -> list[str]:
    """Return citation entries containing unstructured content from Crossref /works for a DOI."""
    url = f"https://api.crossref.org/works/{doi}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    message = response.json().get("message", {})
    references = message.get("reference", [])

    unstructured_citations = []
    for ref in references:
        if isinstance(ref, dict) and "unstructured" in ref:
            unstructured_citations.append(ref["unstructured"])

    return unstructured_citations


if __name__ == "__main__":
    doi = input("Enter DOI: ").strip()
    citations = get_unstructured_citations_for_doi(doi)

    if citations:
        print(f'Found {len(citations)} unstructured citation(s) for DOI: {doi}\n')
        for index, citation in enumerate(citations, start=1):
            print(f"{index}. {citation}")
    else:
        print(f'No unstructured citations found for DOI: {doi}')
