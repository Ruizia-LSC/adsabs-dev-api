import requests


def get_dataset_references_for_doi(doi: str, timeout: int = 30) -> list[dict]:
    """Return references labeled as [Dataset] from Crossref /works for a DOI."""
    url = f"https://api.crossref.org/works/{doi}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    message = response.json().get("message", {})
    references = message.get("reference", [])

    dataset_references = []
    for ref in references:
        if not isinstance(ref, dict):
            continue

        unstructured = ref.get("unstructured", "")
        if "[Dataset]" in unstructured:
            dataset_references.append(ref)

    return dataset_references


if __name__ == "__main__":
    doi = input("Enter DOI: ").strip()
    dataset_refs = get_dataset_references_for_doi(doi)

    if dataset_refs:
        print(f'Found {len(dataset_refs)} cited [Dataset] reference(s) for DOI: {doi}\n')
        for index, ref in enumerate(dataset_refs, start=1):
            print(f"Dataset reference {index}:")
            for key, value in ref.items():
                print(f"  {key}: {value}")
            print()
    else:
        print(f'No cited [Dataset] references found for DOI: {doi}')
