Organization of cited_list10_0_MassExtractions

Extract_DOI_Crossref_Calls.py loads source data from cited_list10_0.json and pulls out all of the metadata for each publication DOI provided by SciX. The example folder is   10.5066_F7P55KJN. 
	
Extract_Datacite_Calls.py loads source data from cited_list10_0.json and pulls out all of the Datacite metadata for the dataset DOI’s provided by SciX. The example folder is DataciteResults_cited_list10_0.

Results.py runs checks for a DataciteResult JSON file against every individual Crossref-call JSON file found in the corresponding sibling Crossref folder. 
The first check is for whether the canonical_doi from the DataciteResults file is found anywhere in an individual Crossref metadata JSON. 
The second test is to see if the "titles" from the DataciteResults file are found anywhere in an individual Crossref metadata JSON. If there is a change in “titles” within the DataciteResults file within “history”, then it also includes whether it is true or false. 
The last test is to print the container where the matching metadata was found. 

Cited_list10_0_massextractions.py combines all three files above (Results.py, Extract_Datacite_Calls.py, and Extract_DOI_Crossref_Calls.py) to run at once, and the output is written to cited_list10_0_MassExtractions/CrossCheckResults. 

Chart_CrossCheckResults.py is code to produce the data found within CrossCheckResults in a visualized format. This includes bar charts, histograms, and pie charts to clearly visualize how much of the pipeline is missing to track citations to datasets from peer-reviewed publications. The resulting PNG files are located in CrossCheckResultsCharts.
