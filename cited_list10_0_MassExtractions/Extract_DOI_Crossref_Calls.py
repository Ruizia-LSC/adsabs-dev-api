import json

citation_doi_list = []

for entry in cited_data:
    # Get the parent DOI. It appears to be a list, so take the first element if available.
    parent_doi_list = entry.get('doi')
    parent_doi = parent_doi_list[0] if parent_doi_list else None

    # Get the list of citation DOIs directly from the entry.
    entry_citation_dois = entry.get('citation_doi', [])

    if parent_doi: # Only proceed if a parent DOI exists
        for citation_doi in entry_citation_dois:
            if citation_doi: # Ensure the citation_doi is not None or empty
                citation_doi_list.append({
                    'parent_doi': parent_doi,
                    'citation_doi': citation_doi
                })

# Display the resulting list
print(f"Found {len(citation_doi_list)} citation DOIs.\n")
# Pretty print all items for better readability
print(json.dumps(citation_doi_list, indent=2))

# You can also display the full list if needed, or save it to a DataFrame

# Step 2
import time
import os # Import the os module to handle file paths and directory creation

def fetch_and_save_crossref_metadata(doi, email_for_polite_pool=None, output_folder='.'):
    """Fetches Crossref metadata for a given DOI and saves it to a JSON file in the specified output folder."""
    crossref_url = f"https://api.crossref.org/works/{doi}"
    # Add a 'mailto' parameter for polite pool usage if an email is provided
    headers = {"User-Agent": f"CitationMetadataFetcher/1.0 (mailto:{email_for_polite_pool})"} if email_for_polite_pool else {}

    # Replace '/' with '_' in the DOI to create a valid filename
    file_name = f"{doi.replace('/', '_')}_CrossrefCall.json"
    file_path = os.path.join(output_folder, file_name)

    try:
        print(f"Fetching metadata for DOI: {doi}")
        response = requests.get(crossref_url, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        crossref_data = response.json()

        # Add the queried URL and original DOI to the metadata
        crossref_data['queried_url'] = crossref_url
        crossref_data['original_doi'] = doi

        with open(file_path, 'w') as f:
            json.dump(crossref_data, f, indent=2)
        print(f"Successfully saved metadata for {doi} to {file_path}")
        return crossref_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching or saving metadata for DOI {doi}: {e}")
        return None

#Step 3
import time
import os # Import the os module to handle file paths and directory creation

# You can optionally provide an email for the Crossref polite pool. Replace 'your-email@example.com' with your actual email.
# This is recommended by Crossref to avoid being blocked if you make many requests.
# user_email = "your-email@example.com" # Uncomment and replace with your email if desired
user_email = None # Or keep None if you don't want to provide an email

# Define the base output folder name
base_output_folder_name = 'DOI_Crossref_Calls_by_ParentDOI'

# Create the base output folder if it doesn't exist
if not os.path.exists(base_output_folder_name):
    os.makedirs(base_output_folder_name)
    print(f"Created base directory: {base_output_folder_name}")

# List to store all fetched metadata (optional, depends on further needs)
all_crossref_metadata = []

print(f"Starting to process {len(citation_doi_list)} citation DOIs...")
for i, entry in enumerate(citation_doi_list):
    citation_doi = entry['citation_doi']
    parent_doi = entry['parent_doi']

    # Sanitize parent_doi to create a valid folder name
    sanitized_parent_doi = parent_doi.replace('/', '_').replace(':', '_')
    specific_output_folder = os.path.join(base_output_folder_name, sanitized_parent_doi)

    # Create the specific parent_doi subfolder if it doesn't exist
    if not os.path.exists(specific_output_folder):
        os.makedirs(specific_output_folder)
        print(f"Created sub-directory for parent DOI '{parent_doi}': {specific_output_folder}")

    metadata = fetch_and_save_crossref_metadata(citation_doi, user_email, output_folder=specific_output_folder)
    if metadata:
        all_crossref_metadata.append({
            'parent_doi': parent_doi,
            'citation_doi': citation_doi,
            'crossref_metadata': metadata
        })
    # Add a delay to respect Crossref API rate limits (e.g., 0.5 seconds per request)
    # This helps avoid overwhelming the API and getting blocked.
    time.sleep(0.5)
    if (i + 1) % 50 == 0: # Print a progress update every 50 DOIs
        print(f"Processed {i + 1}/{len(citation_doi_list)} DOIs.")

print(f"\nFinished processing {len(citation_doi_list)} citation DOIs. Metadata for successful requests saved as individual JSON files in subfolders within the '{base_output_folder_name}' directory.")
print(f"Total metadata items successfully fetched and stored in 'all_crossref_metadata' list: {len(all_crossref_metadata)}")

#Step4 for download

import shutil
import os
from google.colab import files # Import files module for downloading

# Define the folder to be zipped
folder_to_zip = base_output_folder_name # Use the name of the dynamically created folder
# Define the name of the zip file
zip_filename = f'{folder_to_zip}.zip'

if os.path.exists(folder_to_zip):
    print(f"Creating zip archive for '{folder_to_zip}'...")
    shutil.make_archive(folder_to_zip, 'zip', folder_to_zip)
    print(f"Successfully created '{zip_filename}'. You can now download this file from the Colab file browser.")

    # Automatically download the zip file to the user's local machine
    files.download(zip_filename)
else:
    print(f"Error: Folder '{folder_to_zip}' not found. Please ensure the Crossref metadata fetching was successful.")
