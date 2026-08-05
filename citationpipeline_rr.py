# Drafted by GitHub CoPilot based on the previous version of the code.
# Goal in drafting is to be faster and demand less of the Sci-X API.

import json
import requests
from urllib.parse import urlencode

token = "insert_ADS_token_here"
rows = 10
page = 0

test = build_citation_doi_list(token, page=page, rows=rows)
def build_citation_doi_list(token, page=0, rows=100, output_path=None):
    """
    Build dataset citation DOI mapping from ADS API.

    Args:
        token (str): ADS API bearer token.
        page (int): Page index for ADS search results (0-based start offset page).
        rows (int): Number of dataset records to fetch.
        output_path (str|None): Optional output JSON file path.
            Defaults to f'cited_list_page{page}_rows{rows}.json'.

    Returns:
        list: List of dataset records with `citation_doi` added and `citation` removed.
    """

    base_url = "https://api.adsabs.harvard.edu/v1/search/query"
    headers = {"Authorization": f"Bearer {token}"}

    with requests.Session() as s:
        s.headers.update(headers)

        # 1) Fetch dataset docs once
        q = {
            "q": 'doctype:dataset doi:"1*"',
            "fl": "title,bibcode,doi,citation_count,citation",
            "rows": rows,
            "start": page*rows
        }
        r = s.get(f"{base_url}?{urlencode(q)}", timeout=30)
        r.raise_for_status()
        docs = r.json()["response"]["docs"]

        # 2) Keep only cited datasets
        cited_list = [d for d in docs if d.get("citation_count", 0) > 0]

        # 3) Build unique bibcode set across all citations
        all_bibcodes = set()
        for d in cited_list:
            all_bibcodes.update(d.get("citation", []))

        # 4) Batch-resolve bibcodes -> DOI
        bibcode_to_doi = {}
        bibcodes = sorted(all_bibcodes)
        batch_size = 100  # tune based on API behavior

        for i in range(0, len(bibcodes), batch_size):
            chunk = bibcodes[i:i + batch_size]
            # ADS query syntax for many bibcodes in one call
            joined = " OR ".join(chunk)
            q = {
                "q": f"bibcode:({joined})",
                "fl": "bibcode,doi",
                "rows": len(chunk),
            }
            rr = s.get(f"{base_url}?{urlencode(q)}", timeout=30)
            rr.raise_for_status()
            resp_docs = rr.json()["response"]["docs"]

            # default unresolved
            for b in chunk:
                bibcode_to_doi.setdefault(b, None)

            for rec in resp_docs:
                b = rec.get("bibcode")
                dois = [x for x in rec.get("doi", []) if "arXiv" not in x]
                bibcode_to_doi[b] = dois[0] if dois else None

        # 5) Map citation -> citation_doi and remove citation field
        for d in cited_list:
            citation_doi = []
            for b in d.get("citation", []):
                doi = bibcode_to_doi.get(b)
                if doi:
                    citation_doi.append(doi)
            d["citation_doi"] = citation_doi
            d.pop("citation", None)

    with open(f"cited_list{rows}_{page}.json", "w") as f:
        json.dump(cited_list, f, indent=4)
return
