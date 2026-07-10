# Contributed by Alberto Accomazzi
#!/bin/env python
#
# Sample script for querying ADS

# see docs: http://ads.readthedocs.io/en/latest/
from ast import Continue
import ads
import sys
import csv
import json
import argparse


# the list of fields you want to get back from the API
# for a full list, see: http://adsabs.github.io/help/search/comprehensive-solr-term-list
DEF_FIELDS = 'bibcode,title,author,pub,pubdate,citation_count,credit_count,doi,doctype,citation,credit'
DEF_FORMAT = 'jsonl'

# how many records each response will return (max)
DEF_ROWS = 1000

# how many iterations will be run to paginate through results
# note that 
#    tot_records_returned = rows * max_pages
# so one can easily download the entire astronomy database by
# setting max_pages to be 3000, use with caution!
DEF_MAX_PAGES = 2

DEF_SORT = 'date desc,bibcode desc'

bibcode_to_doi_cache = {}
def bibcode_to_doi(bibcodes_list):
    """
    Transforms a bibcode to a DOI using the ADS API, caching the results in a dictionary.
    """
    doi_list = []
    for bibcode in bibcodes_list:
        if bibcode in bibcode_to_doi_cache:
            doi_list.append(bibcode_to_doi_cache[bibcode])
        else:
            # query the ADS API for the DOI
            results = ads.SearchQuery(q=f'identifier:"{bibcode}"', fl='doi,id', rows=1, max_pages=1)
            if results:
                doi_response = results.next()
                if doi_response:
                    rdict = dict(doi_response.iteritems())
                    doi = rdict.get('doi', [])
                    if doi:
                        bibcode_to_doi_cache[bibcode] = doi[0]
                        doi_list.append(doi[0])
    return doi_list

"""
Sends the query as given on the command line to ADS, outputs results to 
stdout (jsonl format)

"""
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f',
        '--fl',
        dest="fl",
        type=str,
        help="List of comma-separated fields to return [default: {}]".format(DEF_FIELDS),
        default=DEF_FIELDS
    )
    parser.add_argument(
        '-r',
        '--rows',
        dest="rows",
        type=int,
        help="Number of rows per page (default: {})".format(DEF_ROWS),
        default=DEF_ROWS
    )
    parser.add_argument(
        '-p',
        '--pages',
        dest="pages",
        type=int,
        help="Number of paginations (default: {})".format(DEF_MAX_PAGES),
        default=DEF_MAX_PAGES
    )
    parser.add_argument(
        '-s',
        '--sort',
        dest="sort",
        type=str,
        help="Sort order (default: {})".format(DEF_SORT),
        default=DEF_SORT
    )
    parser.add_argument(
        '--format',
        dest='format',
        default=DEF_FORMAT,
        help='output format, one of: csv, json, jsonl, key+jsonl (default)'
    )
    parser.add_argument(
        'query',
        nargs='+'
    )

    args = parser.parse_args()
    query = ' '.join(args.query)
    fields = args.fl.split(',')

    # Output from the ADS API is utf-8 clean, so make sure you properly read/write
    #import unicodecsv as csv (python2)

    results = ads.SearchQuery(q=query, 
                              fl=fields + ['id'],  # 'id' field is required by ads module
                              rows=args.rows,
                              max_pages=args.pages,
                              sort=args.sort,
                              )

for record in results:
    rdict = dict(record.iteritems())
    # normalize doi and title
    rdict['doi'] = rdict['doi'][0].strip() if rdict['doi'] else None
    rdict['title'] = rdict['title'][0] if rdict['title'] else None
    # transform citations and credits from bibcodes to DOIs
    # this could be done more efficiently by querying the ADS API for the DOIs in bulk
    # using the bigquery endpoint of the ADS API 
    # (see https://ui.adsabs.harvard.edu/help/api/api-docs.html#post-/search/bigquery)
    rdict['citation_doi'] = bibcode_to_doi(rdict['citation']) if rdict['citation'] else None
    rdict['credit_doi'] = bibcode_to_doi(rdict['credit']) if rdict['credit'] else None
    print(json.dumps(rdict))
