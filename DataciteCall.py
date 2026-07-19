import json

doi_to_fetch = '10.26093/cds/vizier.1350'

try:
    # Fetch the metadata and its history
    metadata_result = fetch_datacite_metadata_with_history(doi_to_fetch)

    # Display the full metadata result
    print("Full Metadata Result for DOI:", doi_to_fetch)
    print(json.dumps(metadata_result, indent=2))

except ValueError as e:
    print(f"Error: {e}")
except requests.exceptions.RequestException as e:
    print(f"Network or API error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
