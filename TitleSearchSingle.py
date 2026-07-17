import requests


def get_dataset_title_from_doi(doi: str, timeout: int = 10) -> str | None:
    """
    Look up a DOI in the Crossref works API and return the dataset title.

    Args:
        doi: The DOI to search for.
        timeout: Request timeout in seconds.

    Returns:
        The first title string if found, otherwise None.
    """
    url = f"https://api.crossref.org/works/{doi}"

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return None
    except ValueError:
        return None

    message = payload.get("message", {})

    # Optional: only treat dataset records as valid
    record_type = message.get("type")
    if record_type and record_type != "dataset":
        return None

    titles = message.get("title", [])
    if isinstance(titles, list) and titles:
        return titles[0]

    return None


if __name__ == "__main__":
    example_doi = "10.5061/dryad.8sf7m0cjw"
    title = get_dataset_title_from_doi(example_doi)

    if title:
        print(f"Dataset title: {title}")
    else:
        print("No dataset title found for that DOI.")
