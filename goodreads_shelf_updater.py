import pandas as pd
import requests
import time
import json
import os
import re
from functools import lru_cache

INPUT_FILE = "goodreads_library_export.csv"
OUTPUT_FILE = "goodreads_cleaned.csv"
CACHE_FILE = "api_cache.json"  # persists between runs so you don't re-hit APIs

# ---------------------------
# PERSISTENT CACHE
# ---------------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

_cache = load_cache()

def cached_get(key, fetch_fn):
    """Generic cache wrapper. key is a string, fetch_fn is a callable."""
    if key in _cache:
        return _cache[key]
    result = fetch_fn()
    _cache[key] = result
    save_cache(_cache)
    return result


# ---------------------------
# GENRE MAPS
# ---------------------------
# Genre mapping removed — the CLI updater now assigns only nationality shelves.
# GENRE_MAP and KEYWORD_MAP intentionally omitted.

# ---------------------------
# NATIONALITY → SHELF MAP
# Wikidata country QIDs → shelf tags
# Covers ~60 countries. Expand as needed.
# ---------------------------

COUNTRY_SHELF_MAP = {
    # English-speaking
    "Q30": "american-fiction",          # United States
    "Q145": "british-fiction",           # United Kingdom
    "Q161885": "british-fiction",        # Great Britain (legacy)
    "Q174193": "british-fiction",        # British Raj (Tagore, Kipling etc.)
    "Q129286": "indian-fiction",         # British India → flag as Indian lit
    "Q668": "indian-fiction",            # India (modern)
    "Q11774": "british-fiction",         # British Empire (Saki, Conan Doyle era)
    "Q170072": "british-fiction",        # Kingdom of Great Britain (pre-1801)
    "Q21": "british-fiction",            # England
    "Q22": "scottish-fiction",           # Scotland
    "Q25": "welsh-fiction",              # Wales
    "Q26": "irish-fiction",              # Northern Ireland
    "Q27": "irish-fiction",              # Ireland (Republic)
    # Historical empires / states
    "Q34266": "russian-literature",      # Russian Empire (Tolstoy, Chekhov, Dostoevsky)
    "Q15180": "russian-literature",      # Soviet Union (Bulgakov, Pasternak)
    "Q33946": "czech-fiction",           # Czechoslovakia (Kafka, Kundera)
    "Q131964": "austro-hungarian-fiction", # Austro-Hungarian Empire
    "Q28513": "ottoman-fiction",         # Ottoman Empire
    "Q43287": "german-fiction",          # German Empire (pre-1918)
    "Q713750": "german-fiction",         # Weimar Republic
    "Q7318": "german-fiction",           # Nazi Germany (for authors born there)
    "Q1747689": "american-fiction",      # Colonial America (pre-independence authors)
    "Q193714": "irish-fiction",          # Irish Free State
    "Q212429": "french-fiction",         # French Third Republic
    "Q70972": "french-fiction",          # French First Republic / Empire era
    "Q142": "french-fiction",            # France
    "Q183": "german-fiction",            # Germany
    "Q38": "italian-fiction",            # Italy
    "Q29": "spanish-fiction",            # Spain
    "Q45": "portuguese-fiction",         # Portugal
    "Q155": "latin-american-fiction",    # Brazil
    "Q414": "latin-american-fiction",    # Argentina
    "Q96": "latin-american-fiction",     # Mexico
    "Q241": "latin-american-fiction",    # Cuba
    "Q298": "latin-american-fiction",    # Chile
    "Q739": "latin-american-fiction",    # Colombia
    "Q717": "latin-american-fiction",    # Venezuela
    "Q419": "latin-american-fiction",    # Peru
    "Q750": "latin-american-fiction",    # Bolivia
    "Q77": "latin-american-fiction",     # Uruguay
    "Q733": "latin-american-fiction",    # Paraguay
    "Q736": "latin-american-fiction",    # Ecuador
    "Q17": "japanese-literature",        # Japan
    "Q148": "chinese-literature",        # China (PRC)
    "Q865": "chinese-literature",        # Taiwan
    "Q884": "korean-literature",         # South Korea
    "Q423": "korean-literature",         # North Korea
    "Q668": "indian-fiction",            # India
    "Q159": "russian-literature",        # Russia
    "Q15180": "russian-literature",      # Soviet Union (historical)
    "Q33946": "czech-fiction",           # Czechoslovakia (historical)
    "Q213": "czech-fiction",             # Czech Republic
    "Q214": "czech-fiction",             # Slovakia
    "Q224": "balkan-fiction",            # Croatia
    "Q217": "balkan-fiction",            # Moldova
    "Q36": "polish-fiction",             # Poland
    "Q37": "baltic-fiction",             # Lithuania
    "Q33": "nordic-fiction",             # Finland
    "Q35": "nordic-fiction",             # Denmark
    "Q34": "nordic-fiction",             # Sweden
    "Q20": "nordic-fiction",             # Norway
    "Q189": "nordic-fiction",            # Iceland
    "Q55": "dutch-fiction",              # Netherlands
    "Q31": "dutch-fiction",              # Belgium (Flemish)
    "Q39": "swiss-fiction",              # Switzerland
    "Q40": "austrian-fiction",           # Austria
    "Q224": "balkan-fiction",            # Croatia
    "Q403": "balkan-fiction",            # Serbia
    "Q219": "balkan-fiction",            # Bulgaria
    "Q218": "romanian-fiction",          # Romania
    "Q41": "greek-fiction",              # Greece
    "Q43": "turkish-fiction",            # Turkey
    "Q801": "israeli-fiction",           # Israel
    "Q796": "middle-eastern-fiction",    # Iraq
    "Q794": "middle-eastern-fiction",    # Iran (Persia)
    "Q858": "arabic-fiction",            # Syria
    "Q79": "arabic-fiction",             # Egypt
    "Q1049": "african-fiction",          # Sudan
    "Q916": "african-fiction",           # Angola
    "Q258": "african-fiction",           # South Africa
    "Q114": "african-fiction",           # Kenya
    "Q117": "african-fiction",           # Ghana
    "Q1006": "west-african-fiction",     # Guinea
    "Q1007": "west-african-fiction",     # Guinea-Bissau
    "Q1008": "west-african-fiction",     # Ivory Coast
    "Q912": "west-african-fiction",      # Mali
    "Q786": "caribbean-fiction",         # Jamaica
    "Q769": "caribbean-fiction",         # Saint Lucia
    "Q781": "caribbean-fiction",         # Barbados
    "Q771": "caribbean-fiction",         # Trinidad and Tobago
    "Q16": "canadian-fiction",           # Canada
    "Q408": "australian-fiction",        # Australia
    "Q664": "new-zealand-fiction",       # New Zealand
    "Q711": "new-zealand-fiction",       # New Zealand (alt)
    "Q851": "south-asian-fiction",       # Pakistan
    "Q902": "south-asian-fiction",       # Bangladesh
    "Q837": "south-asian-fiction",       # Nepal
    "Q854": "south-asian-fiction",       # Sri Lanka
    "Q252": "southeast-asian-fiction",   # Indonesia
    "Q928": "southeast-asian-fiction",   # Philippines
    "Q833": "southeast-asian-fiction",   # Malaysia
    "Q334": "southeast-asian-fiction",   # Singapore
    "Q869": "southeast-asian-fiction",   # Thailand
    "Q881": "southeast-asian-fiction",   # Vietnam
}


# ---------------------------
# WIKIDATA NATIONALITY LOOKUP
# ---------------------------

def _search_wikidata_author(author_name):
    """
    Search Wikidata for an author entity, then retrieve their country of
    citizenship (P27). Returns a list of Wikidata country QIDs.
    No API key required — but Wikidata requires a descriptive User-Agent
    header or it returns an empty response.
    """
    # Wikidata policy: identify your client or requests are silently dropped.
    headers = {
        "User-Agent": "GoodreadsShelfUpdater/1.0 (youremail@example.com)"
    }

    try:
        # Step 1: search for the entity
        search_url = "https://www.wikidata.org/w/api.php"
        search_params = {
            "action": "wbsearchentities",
            "search": author_name,
            "language": "en",
            "type": "item",
            "limit": 5,
            "format": "json",
        }
        res = requests.get(search_url, params=search_params, headers=headers, timeout=8)

        if not res.content:
            print(f"  ⚠ Wikidata returned empty response for '{author_name}' (missing User-Agent accepted?)")
            return []

        results = res.json().get("search", [])

        if not results:
            return []

        # Pick the best match: prefer items described as "human", "author",
        # "writer", "novelist" etc. in their description
        author_keywords = {"human", "writer", "author", "novelist", "poet",
                           "playwright", "journalist", "essayist", "screenwriter"}
        entity_id = None
        for r in results:
            desc = r.get("description", "").lower()
            if any(kw in desc for kw in author_keywords):
                entity_id = r["id"]
                break
        # Fall back to first result if none matched description
        if not entity_id and results:
            entity_id = results[0]["id"]

        if not entity_id:
            return []

        # Step 2: fetch the entity's claims
        entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
        entity_res = requests.get(entity_url, headers=headers, timeout=8)

        if not entity_res.content:
            return []

        entity_data = entity_res.json()

        claims = entity_data.get("entities", {}).get(entity_id, {}).get("claims", {})

        # P27 = country of citizenship
        citizenship_claims = claims.get("P27", [])
        country_qids = []
        for claim in citizenship_claims:
            mainsnak = claim.get("mainsnak", {})
            if mainsnak.get("snaktype") == "value":
                qid = mainsnak.get("datavalue", {}).get("value", {}).get("id")
                if qid:
                    country_qids.append(qid)

        return country_qids

    except Exception as e:
        print(f"  ⚠ Wikidata lookup failed for '{author_name}': {e}")
        return []


def get_author_nationality_shelves(author):
    """
    Returns a set of shelf tags derived from the author's Wikidata nationality.
    Results are cached by author name.
    """
    # Canonicalize author for cache keys: collapse whitespace, lowercase
    def _normalize_author_key(name):
        return re.sub(r"\s+", " ", str(name).strip().lower())

    normalized_author = _normalize_author_key(author)
    cache_key = f"wikidata_author::{normalized_author}"

    # Fast path: exact normalized key exists
    if cache_key in _cache:
        country_qids = _cache[cache_key]
    else:
        # Try to find an existing wikidata_author entry whose stored name
        # canonicalizes to the same normalized form (handles spacing/punctuations).
        country_qids = None
        for k, v in _cache.items():
            if k.startswith("wikidata_author::"):
                stored = k.split("::", 1)[1]
                if _normalize_author_key(stored) == normalized_author:
                    country_qids = v
                    # Migrate value to the canonical normalized key for future runs
                    if k != cache_key:
                        _cache[cache_key] = v
                        save_cache(_cache)
                    break

        # If still not found, fetch and cache under the normalized key
        if country_qids is None:
                country_qids = cached_get(cache_key, lambda: _search_wikidata_author(normalized_author))

    shelves = set()
    for qid in country_qids:
        shelf = COUNTRY_SHELF_MAP.get(qid)
        if shelf:
            shelves.add(shelf)
        else:
            print(f"  – Unmapped Wikidata QID: {qid} — add to COUNTRY_SHELF_MAP if needed")

    return shelves


# ---------------------------
# GENRE API FUNCTIONS
# ---------------------------

def get_google_books_genres(title, author, isbn=None):
    def _compact(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())

    key_part = isbn if isbn else title.lower()
    cache_key = f"google_books::{key_part}::{author.lower()}"

    # Reuse or migrate existing cached google_books entries (title/author variants)
    for k, v in _cache.items():
        if not k.startswith("google_books::"):
            continue
        try:
            _, stored_keypart, stored_author = k.split("::", 2)
        except ValueError:
            continue
        # Only reuse cached positive results; if previous run stored an empty
        # list, prefer refetching (helps recover from earlier failed queries)
        if not v:
            continue

        # If exact isbn stored, reuse it
        if isbn and stored_keypart == isbn:
            if k != cache_key:
                _cache[cache_key] = v
                save_cache(_cache)
            return v

        # If title/author compact match, reuse and migrate
        if not isbn:
            if _compact(stored_keypart) == _compact(title) and _compact(stored_author) == _compact(author):
                if k != cache_key:
                    _cache[cache_key] = v
                    save_cache(_cache)
                return v

    def fetch():
        try:
            # Prefer ISBN lookup when available for exact matches
            if isbn:
                query = requests.utils.quote(f"isbn:{isbn}")
            else:
                query = requests.utils.quote(f"{title} {author}")

            url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=10"
            res = requests.get(url, timeout=8).json()
            items = res.get("items", []) if res else []
            if not items:
                return []

            # Score items to prefer exact matches (industryIdentifiers, title/author match)
            def _score_item(it):
                score = 0
                v = it.get("volumeInfo", {})
                title_match = _compact(v.get("title", ""))
                if isbn:
                    for ii in v.get("industryIdentifiers", []):
                        ident = str(ii.get("identifier", ""))
                        if isbn in ident:
                            score += 50
                # title similarity
                if _compact(title) and _compact(title) in title_match:
                    score += 10
                # author similarity
                authors = " ".join(v.get("authors", [])).lower()
                if author and author.lower() in authors:
                    score += 8
                # categories presence
                if v.get("categories"):
                    score += 2
                return score

            scored = [(it, _score_item(it)) for it in items]
            scored.sort(key=lambda x: x[1], reverse=True)

            # Prefer highest scoring item's categories; if empty, collect from others
            genres = []
            if scored and scored[0][1] > 0:
                top_cats = scored[0][0].get("volumeInfo", {}).get("categories", []) or []
                genres.extend(top_cats)

            # If no categories yet, aggregate categories from any item that has them
            if not genres:
                for it, _ in scored:
                    cats = it.get("volumeInfo", {}).get("categories", [])
                    if cats:
                        genres.extend(cats)
            # Normalize to unique list preserving order
            seen = set()
            out = []
            for g in genres:
                if g not in seen:
                    seen.add(g)
                    out.append(g)
            return out
        except Exception as e:
            print(f"  ⚠ Google Books error: {e}")
            return []

    # Genre lookups are disabled in the nationality-only mode.
    return []


def get_openlibrary_genres(title, author="", isbn=None):
    def _compact(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())

    key_part = isbn if isbn else title.lower()
    cache_key = f"openlibrary::{key_part}::{author.lower()}"

    # Reuse/migrate existing cached openlibrary entries
    for k, v in _cache.items():
        if not k.startswith("openlibrary::"):
            continue
        try:
            _, stored_keypart, stored_author = k.split("::", 2)
        except ValueError:
            continue
        # Skip empty cached results to allow refetching
        if not v:
            continue

        if isbn and stored_keypart == isbn:
            if k != cache_key:
                _cache[cache_key] = v
                save_cache(_cache)
            return v

        if not isbn and _compact(stored_keypart) == _compact(title) and _compact(stored_author) == _compact(author):
            if k != cache_key:
                _cache[cache_key] = v
                save_cache(_cache)
            return v

    def fetch():
        try:
            # If ISBN available, use the ISBN API which often includes subjects
            if isbn:
                url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=data&format=json"
                res = requests.get(url, timeout=8).json()
                key = f"ISBN:{isbn}"
                if not res or key not in res:
                    # fallback to search by ISBN via search.json
                    url = f"https://openlibrary.org/search.json?isbn={isbn}&limit=5"
                    res2 = requests.get(url, timeout=8).json()
                    docs = res2.get("docs", [])
                    subjects = []
                    for doc in docs:
                        subjects.extend(doc.get("subject", []))
                    return subjects
                book = res.get(key, {})
                subjects = []
                for s in book.get("subjects", []):
                    if isinstance(s, dict):
                        name = s.get("name")
                        if name:
                            subjects.append(name)
                    elif isinstance(s, str):
                        subjects.append(s)
                return subjects

            # Fallback to search by title/author
            query = requests.utils.quote(f"{title} {author}".strip())
            url = f"https://openlibrary.org/search.json?q={query}&limit=10"
            res = requests.get(url, timeout=8).json()
            if "docs" not in res or not res["docs"]:
                return []
            subjects = []
            # Prefer docs that contain subjects
            for doc in res["docs"][:10]:
                if doc.get("subject"):
                    subjects.extend(doc.get("subject", []))
            return subjects
        except Exception as e:
            print(f"  ⚠ Open Library error: {e}")
            return []

    # Genre lookups are disabled in the nationality-only mode.
    return []


# ---------------------------
# GENRE NORMALIZATION
# ---------------------------

def normalize_genres(raw_genres):
    """
    Match raw genre strings (from APIs) against GENRE_MAP and KEYWORD_MAP.
    Returns a set of normalized shelf tags.
    """
    # Genre normalization removed — return empty set.
    return set()


# ---------------------------
# MAIN PROCESSING
# ---------------------------

def process_books(df):
    new_shelves = []
    log = []

    for idx, row in df.iterrows():
        title = str(row.get("Title", "")).strip()
        author = str(row.get("Author", "")).strip()
        existing_raw = str(row.get("Bookshelves", ""))

        print(f"\n[{idx+1}/{len(df)}] {title} — {author}")

        # Parse existing shelves (supports comma-separated or space-separated)
        existing_tags = set()
        if existing_raw and existing_raw.lower() != "nan":
            if "," in existing_raw:
                parts = [p.strip() for p in existing_raw.split(",") if p.strip()]
            else:
                parts = [p.strip() for p in re.split(r"\s+", existing_raw.strip()) if p.strip()]
            for s in parts:
                # remove position suffixes like "(#123)" and trim
                s_clean = re.sub(r"\s*\(.*\)\s*$", "", s).strip()
                if s_clean:
                    existing_tags.add(s_clean)

        # Status shelves we want to exclude from Bookshelves
        def _is_status_tag(t):
            tn = re.sub(r"\s*\(.*\)\s*$", "", str(t).strip().lower())
            tn = re.sub(r"\s+", "-", tn)
            statuses = {"to-read", "currently-reading", "read"}
            for st in statuses:
                if tn == st or tn.startswith(st):
                    return True
            return False

        filtered = {t for t in existing_tags if not _is_status_tag(t)}

        # Prefer ISBN-based lookups when possible (use ISBN13 then ISBN)
        isbn = None
        for col in ("ISBN13", "ISBN"):
            raw = str(row.get(col, "")).strip()
            if raw and raw.lower() != "nan":
                cleaned = re.sub(r"[^0-9Xx]", "", raw)
                if cleaned:
                    isbn = cleaned
                    break

        # Wikidata author nationality → shelf
        nat_shelves = get_author_nationality_shelves(author)
        if nat_shelves:
            print(f"  ✓ Wikidata nationality: {nat_shelves}")
        else:
            print(f"  – Wikidata: no nationality found")

        merged = set(filtered)
        merged.update(nat_shelves)

        # Normalize: lowercase, hyphenate internal spaces, drop empties
        normalized = {
            re.sub(r"\s+", "-", s.strip().lower())
            for s in merged if s and s.lower() != "nan"
        }

        # Bookshelves should be space-separated per user's preference
        bookshelves_str = " ".join(sorted(normalized))
        new_shelves.append(bookshelves_str)
        log.append({"title": title, "author": author, "shelves": bookshelves_str})

        time.sleep(0.4)  # polite rate limiting

    df = df.copy()
    df["Bookshelves"] = new_shelves
    # Shelves column should mirror the Exclusive Shelf column
    if "Exclusive Shelf" in df.columns:
        df["Shelves"] = df["Exclusive Shelf"]
    else:
        df["Shelves"] = ""

    # Reorder columns: core set first, then preserve any other original columns
    core_cols = [
        "Title", "Author", "ISBN", "My Rating", "Average Rating", "Publisher",
        "Binding", "Year Published", "Original Publication Year", "Date Read",
        "Date Added", "Shelves", "Bookshelves", "My Review"
    ]
    orig_cols = list(df.columns)
    other_cols = [c for c in orig_cols if c not in core_cols]
    final_cols = [c for c in core_cols if c in df.columns] + other_cols
    df = df.reindex(columns=final_cols)
    return df, log


# ---------------------------
# RUN
# ---------------------------

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: '{INPUT_FILE}' not found. Export your Goodreads library first.")
        return

    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df)} books from {INPUT_FILE}\n")

    df, log = process_books(df)

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Done! Saved to: {OUTPUT_FILE}")

    # Summary
    total_shelves = sum(len(r["shelves"].split()) for r in log if r["shelves"])
    print(f"\n📊 Summary:")
    print(f"   Books processed : {len(log)}")
    print(f"   Total shelves   : {total_shelves}")
    print(f"   Avg per book    : {total_shelves / max(len(log), 1):.1f}")

    # Show books with no shelves detected
    missing = [r for r in log if not r["shelves"]]
    if missing:
        print(f"\n⚠  No shelves found for {len(missing)} books:")
        for r in missing:
            print(f"   - {r['title']} by {r['author']}")


if __name__ == "__main__":
    main()