import json
import os
import re

# ── Configuration ──────────────────────────────────────────────────────────────
CROSSREF_FOLDER   = "10.26093_cds_vizier.1350"       # folder of Crossref call JSONs
DATACITE_FOLDER   = "DataciteResults"                 # folder of Datacite result JSONs
OUTPUT_FILE_TITLES= "crossref_datacite_title_matches.json"
# ───────────────────────────────────────────────────────────────────────────────


def load_datacite_titles(datacite_folder: str) -> list[str]:
    """
    Walk every JSON file in datacite_folder and collect unique titles.
    Returns a deduplicated list (case-preserved, but lookup is case-insensitive).
    """
    seen = set()
    titles = []

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

        candidate_titles = []

        # Helper function to extract titles from a 'titles' list, handling both string and dict formats
        def _extract_titles_from_list(titles_list):
            if isinstance(titles_list, list):
                for t_entry in titles_list:
                    if isinstance(t_entry, str): # Handle titles as direct strings in list
                        candidate_titles.append(t_entry)
                    elif isinstance(t_entry, dict) and 'title' in t_entry: # Handle titles as dicts with 'title' key
                        candidate_titles.append(t_entry['title'])

        # Check for titles in the 'current' object
        current_data = rec.get('current', {})
        _extract_titles_from_list(current_data.get('titles'))
        # Also check for a direct 'title' field in 'current' object
        if 'title' in current_data and isinstance(current_data['title'], str):
            candidate_titles.append(current_data['title'])

        # Check for titles in the 'history' objects
        for hist_entry in rec.get('history', []):
            if isinstance(hist_entry, dict):
                _extract_titles_from_list(hist_entry.get('titles'))
                # Also check for a direct 'title' field in 'history' entry
                if 'title' in hist_entry and isinstance(hist_entry['title'], str):
                    candidate_titles.append(hist_entry['title'])

        # Also check directly at the top level
        _extract_titles_from_list(rec.get('titles'))
        # Also check for a direct 'title' field at the top level
        if 'title' in rec and isinstance(rec['title'], str):
            candidate_titles.append(rec['title'])

        for extracted_title in candidate_titles:
            if extracted_title and extracted_title.strip():
                normalized_title = extracted_title.strip().lower()
                if normalized_title not in seen:
                    seen.add(normalized_title)
                    titles.append(extracted_title.strip())
    return titles


def _search_json_value(value, target_phrases: set[str], path: str = "$"):
    """
    Recursively walk a parsed JSON structure and return the first
    (matched_target_phrase, json_path, matched_text) tuple, or None.
    `target_phrases` is a set of lower-cased title strings for fast lookup.
    """
    if isinstance(value, str):
        hay = value.lower()
        for t in target_phrases:
            if t in hay:
                return t, path, value
        return None

    if isinstance(value, dict):
        for k, v in value.items():
            result = _search_json_value(v, target_phrases, f"{path}.{k}")
            if result:
                return result
        return None

    if isinstance(value, list):
        for i, item in enumerate(value):
            result = _search_json_value(item, target_phrases, f"{path}[{i}]")
            if result:
                return result
        return None

    return None  # numbers, booleans, null


def find_all_matches_in_file(
    fpath: str,
    target_titles_lower: set[str],
    title_map_lower_to_original: dict[str, str],
) -> list[dict]:
    """
    Parse one Crossref JSON file and return ALL Datacite title matches found
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
    for title_lower in sorted(target_titles_lower):
        result = _search_json_value(data, {title_lower})
        if result:
            _matched_lower, json_path, matched_text = result
            original_title = title_map_lower_to_original.get(title_lower, title_lower)

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
                    "matched_datacite_title": original_title,
                    "json_path": json_path,
                    "matched_text": matched_text,
                    "reference_object": reference_obj,
                }
            )

    return matches


def main():
    # ── 1. Load Datacite titles ─────────────────────────────────────────────────
    print(f"Loading Datacite titles from '{DATACITE_FOLDER}' …")
    datacite_titles = load_datacite_titles(DATACITE_FOLDER)
    print(f"  → {len(datacite_titles)} unique Datacite titles loaded.\n")

    if not datacite_titles:
        print("No Datacite titles found – nothing to search for. Exiting.")
        return

    # Build a lower-cased set for fast matching and a reverse map
    title_lower_set         = {t.lower() for t in datacite_titles}
    title_map_lower_to_orig = {t.lower(): t for t in datacite_titles}

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
        matches = find_all_matches_in_file(fpath, title_lower_set, title_map_lower_to_orig)

        if not matches:
            files_with_no_matches.append(fname)

        for m in matches:
            print(f"[MATCH] File       : {m['crossref_file']}")
            print(f"        Crossref DOI: {m['crossref_doi']}")
            print(f"        Datacite Title: {m['matched_datacite_title']}")
            print(f"        Location    : {m['json_path']}")
            print(f"        Text        : {m['matched_text'][:120]}")
            if m["reference_object"]:
                print("        Ref object  :", json.dumps(m["reference_object"], ensure_ascii=False))
            print()

        all_matches.extend(matches)

        if i % 50 == 0:
            print(f"  … processed {i}/{len(crossref_files)} files, {len(all_matches)} matches so far …\n")

    # ── 3. Save results ───────────────────────────────────────────────────────
    with open(OUTPUT_FILE_TITLES, "w", encoding="utf-8") as f:
        json.dump(all_matches, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Done. {len(all_matches)} match(es) found across {len(crossref_files)} files.")
    print(f"Results saved to '{OUTPUT_FILE_TITLES}'.")

    # Print files with no matches
    if files_with_no_matches:
        print(f"\nFiles with no matching titles ({len(files_with_no_matches)}):")
        for no_match_file in files_with_no_matches:
            print(f"- {no_match_file}")
    else:
        print("\nAll Crossref files contained at least one matching title.")


if __name__ == "__main__":
    main()
