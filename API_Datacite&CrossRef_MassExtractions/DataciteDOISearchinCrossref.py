import json
import os
import re

# ── Configuration ──────────────────────────────────────────────────────────────
CROSSREF_FOLDER   = "10.26093_cds_vizier.1350"       # folder of Crossref call JSONs
DATACITE_FOLDER   = "DataciteResults"                 # folder of Datacite result JSONs
OUTPUT_FILE       = "crossref_datacite_doi_matches.json"
# ───────────────────────────────────────────────────────────────────────────────


def load_datacite_dois(datacite_folder: str) -> list[str]:
    """
    Walk every JSON file in datacite_folder and collect unique DOIs from the
    fields: query_doi, canonical_doi, and current.doi / history[*].doi / doi.
    Returns a deduplicated list (case-preserved, but lookup is case-insensitive).
    """
    seen  = set()
    dois  = []

    if not os.path.isdir(datacite_folder):
        raise FileNotFoundError(f"DataciteResults folder not found: {datacite_folder!r}")

    for fname in sorted(os.listdir(datacite_folder)):
        if not fname.lower().endswith(".json"):
            continue
        fpath = os.path.join(datacite_folder, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[WARN] Could not read {fpath}: {exc}")
            continue

        def _add(val):
            if isinstance(val, str) and val.strip():
                norm = val.strip().lower()
                if norm not in seen:
                    seen.add(norm)
                    dois.append(val.strip())

        # Top-level scalar DOI fields
        for key in ("query_doi", "canonical_doi", "doi"):
            _add(rec.get(key))

        # Nested: current.doi
        current = rec.get("current", {})
        if isinstance(current, dict):
            _add(current.get("doi"))
            _add(current.get("id"))

        # Nested: history[*].doi
        for hist_entry in rec.get("history", []):
            if isinstance(hist_entry, dict):
                _add(hist_entry.get("doi"))
                _add(hist_entry.get("id"))

    return dois


def _search_json_value(value, targets: set[str], path: str = "$"):
    """
    Recursively walk a parsed JSON structure and return the first
    (matched_target_doi, json_path, matched_text) tuple, or None.
    `targets` is a set of lower-cased DOI strings for fast lookup.
    """
    if isinstance(value, str):
        hay = value.lower()
        for t in targets:
            if t in hay:
                return t, path, value
        return None

    if isinstance(value, dict):
        for k, v in value.items():
            result = _search_json_value(v, targets, f"{path}.{k}")
            if result:
                return result
        return None

    if isinstance(value, list):
        for i, item in enumerate(value):
            result = _search_json_value(item, targets, f"{path}[{i}]")
            if result:
                return result
        return None

    return None  # numbers, booleans, null


def find_all_matches_in_file(
    fpath: str,
    target_dois_lower: set[str],
    doi_map_lower_to_original: dict[str, str],
) -> list[dict]:
    """
    Parse one Crossref JSON file and return ALL Datacite DOI matches found
    anywhere in the document, each as a dict with context info.
    """
    try:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[WARN] Could not read {fpath}: {exc}")
        return []

    matches = []
    # We want to find every match, not just the first, so we iterate over targets.
    # For large files this is acceptable; optimise with regex multi-pattern if needed.
    for doi_lower in sorted(target_dois_lower):
        result = _search_json_value(data, {doi_lower})
        if result:
            _matched_lower, json_path, matched_text = result
            original_doi = doi_map_lower_to_original.get(doi_lower, doi_lower)

            # If the match is inside $.message.reference[N], capture that object
            reference_obj = None
            m = re.match(r"^\$.message\.reference\[(\d+)\](?:\.|$)", json_path)
            if m:
                idx = int(m.group(1))
                refs = data.get("message", {}).get("reference")
                if isinstance(refs, list) and 0 <= idx < len(refs):
                    reference_obj = refs[idx]

            matches.append(
                {
                    "crossref_file": os.path.basename(fpath),
                    "crossref_doi": (
                        data.get("message", {}).get("DOI")
                        or data.get("original_doi")
                        or ""
                    ),
                    "matched_datacite_doi": original_doi,
                    "json_path": json_path,
                    "matched_text": matched_text,
                    "reference_object": reference_obj,
                }
            )

    return matches


def main():
    # ── 1. Load Datacite DOIs ─────────────────────────────────────────────────
    print(f"Loading Datacite DOIs from '{DATACITE_FOLDER}' …")
    datacite_dois = load_datacite_dois(DATACITE_FOLDER)
    print(f"  → {len(datacite_dois)} unique Datacite DOIs loaded.\n")

    if not datacite_dois:
        print("No Datacite DOIs found – nothing to search for. Exiting.")
        return

    # Build a lower-cased set for fast matching and a reverse map
    doi_lower_set         = {d.lower() for d in datacite_dois}
    doi_map_lower_to_orig = {d.lower(): d for d in datacite_dois}

    # ── 2. Scan Crossref files ────────────────────────────────────────────────
    if not os.path.isdir(CROSSREF_FOLDER):
        raise FileNotFoundError(f"Crossref folder not found: {CROSSREF_FOLDER!r}")

    crossref_files = sorted(
        f for f in os.listdir(CROSSREF_FOLDER)
        if f.lower().endswith(".json")
    )
    print(f"Scanning {len(crossref_files)} Crossref JSON files in '{CROSSREF_FOLDER}' …\n")

    all_matches = []
    files_with_no_matches = [] # New list to store files with no matches

    for i, fname in enumerate(crossref_files, 1):
        fpath   = os.path.join(CROSSREF_FOLDER, fname)
        matches = find_all_matches_in_file(fpath, doi_lower_set, doi_map_lower_to_orig)

        if not matches: # Check if no matches were found for the current file
            files_with_no_matches.append(fname)

        for m in matches:
            print(f"[MATCH] File       : {m['crossref_file']}")
            print(f"        Crossref DOI: {m['crossref_doi']}")
            print(f"        Datacite DOI: {m['matched_datacite_doi']}")
            print(f"        Location    : {m['json_path']}")
            print(f"        Text        : {m['matched_text'][:120]}")
            if m["reference_object"]:
                print("        Ref object  :", json.dumps(m["reference_object"], ensure_ascii=False))
            print()

        all_matches.extend(matches)

        if i % 50 == 0:
            print(f"  … processed {i}/{len(crossref_files)} files, {len(all_matches)} matches so far …\n")

    # ── 3. Save results ───────────────────────────────────────────────────────
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_matches, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Done. {len(all_matches)} match(es) found across {len(crossref_files)} files.")
    print(f"Results saved to '{OUTPUT_FILE}'.")

    # Print files with no matches
    if files_with_no_matches:
        print(f"\nFiles with no matching DOIs ({len(files_with_no_matches)}):")
        for no_match_file in files_with_no_matches:
            print(f"- {no_match_file}")
    else:
        print("\nAll Crossref files contained at least one matching DOI.")


if __name__ == "__main__":
    main()
