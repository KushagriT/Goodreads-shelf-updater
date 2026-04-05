import streamlit as st
import pandas as pd
import requests
import time
import json
import os
import re
import io

# ---------------------------
# PAGE CONFIG
# ---------------------------

st.set_page_config(
    page_title="Goodreads Shelf Updater",
    page_icon="📚",
    layout="centered",
)

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Source+Sans+3:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'Source Sans 3', sans-serif;
        }
        h1, h2, h3 {
            font-family: 'Playfair Display', serif;
        }
        .main { max-width: 720px; margin: auto; }

        .stAlert { border-radius: 8px; }

        div[data-testid="stFileUploader"] {
            border: 2px dashed #c9a96e;
            border-radius: 10px;
            padding: 1rem;
            background: #fdfaf5;
        }
        .shelf-tag {
            display: inline-block;
            background: #f0e6d3;
            color: #5c3d1e;
            border-radius: 20px;
            padding: 3px 12px;
            margin: 3px;
            font-size: 0.82rem;
            font-weight: 500;
        }
        .stat-box {
            background: #fdfaf5;
            border: 1px solid #e8d9c0;
            border-radius: 10px;
            padding: 1.2rem 1.5rem;
            text-align: center;
        }
        .stat-number {
            font-family: 'Playfair Display', serif;
            font-size: 2.2rem;
            color: #5c3d1e;
            line-height: 1;
        }
        .stat-label {
            font-size: 0.85rem;
            color: #9e7a50;
            margin-top: 4px;
        }
    </style>
""", unsafe_allow_html=True)

# ---------------------------
# MAPS (same as script)
# ---------------------------

# Genre mapping removed — this app now assigns nationality-only shelves.
# GENRE_MAP and KEYWORD_MAP intentionally omitted.

COUNTRY_SHELF_MAP = {
    "Q30": "american-fiction", "Q145": "british-fiction",
    "Q174193": "british-fiction", "Q129286": "indian-fiction",
    "Q668": "indian-fiction", "Q11774": "british-fiction",
    "Q170072": "british-fiction", "Q21": "british-fiction",
    "Q22": "scottish-fiction", "Q25": "welsh-fiction",
    "Q26": "irish-fiction", "Q27": "irish-fiction",
    "Q34266": "russian-literature", "Q15180": "russian-literature",
    "Q33946": "czech-fiction", "Q131964": "austro-hungarian-fiction",
    "Q142": "french-fiction", "Q183": "german-fiction",
    "Q43287": "german-fiction", "Q713750": "german-fiction",
    "Q38": "italian-fiction", "Q29": "spanish-fiction",
    "Q45": "portuguese-fiction", "Q155": "latin-american-fiction",
    "Q414": "latin-american-fiction", "Q96": "latin-american-fiction",
    "Q241": "latin-american-fiction", "Q298": "latin-american-fiction",
    "Q739": "latin-american-fiction", "Q17": "japanese-literature",
    "Q148": "chinese-literature", "Q865": "chinese-literature",
    "Q884": "korean-literature", "Q159": "russian-literature",
    "Q36": "polish-fiction", "Q33": "nordic-fiction",
    "Q35": "nordic-fiction", "Q34": "nordic-fiction",
    "Q20": "nordic-fiction", "Q189": "nordic-fiction",
    "Q55": "dutch-fiction", "Q39": "swiss-fiction",
    "Q40": "austrian-fiction", "Q41": "greek-fiction",
    "Q43": "turkish-fiction", "Q801": "israeli-fiction",
    "Q794": "middle-eastern-fiction", "Q79": "arabic-fiction",
    "Q258": "african-fiction", "Q114": "african-fiction",
    "Q786": "caribbean-fiction", "Q769": "caribbean-fiction",
    "Q771": "caribbean-fiction", "Q16": "canadian-fiction",
    "Q408": "australian-fiction", "Q664": "new-zealand-fiction",
    "Q851": "south-asian-fiction", "Q252": "southeast-asian-fiction",
    "Q928": "southeast-asian-fiction", "Q869": "southeast-asian-fiction",
    "Q881": "southeast-asian-fiction",
}

# ---------------------------
# SESSION CACHE
# Persists across reruns within the same session
# ---------------------------

if "api_cache" not in st.session_state:
    st.session_state.api_cache = {}

def cached_get(key, fetch_fn):
    if key in st.session_state.api_cache:
        return st.session_state.api_cache[key]
    result = fetch_fn()
    st.session_state.api_cache[key] = result
    return result

# ---------------------------
# API FUNCTIONS
# ---------------------------

def get_headers(email):
    return {
        "User-Agent": f"GoodreadsShelfUpdater/1.0 (personal project; {email})"
    }
def get_wikidata_book_genres(title, author, email, isbn=None):
    # Book-level genre lookup removed — this app no longer queries P136.
    return []

def get_wikidata_nationality(author, email):
    # Normalize internal spacing to avoid issues from multiple spaces
    normalized_author = re.sub(r"\s+", " ", str(author).strip())
    cache_key = f"wikidata::{normalized_author.lower()}"
    headers = get_headers(email)
    def fetch():
        try:
            search_url = "https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbsearchentities",
                "search": normalized_author,
                "language": "en",
                "type": "item",
                "limit": 5,
                "format": "json",
            }
            res = requests.get(search_url, params=params, headers=headers, timeout=8)
            if not res.content:
                return []
            results = res.json().get("search", [])
            if not results:
                return []

            author_keywords = {"human", "writer", "author", "novelist", "poet",
                               "playwright", "journalist", "essayist", "screenwriter"}
            entity_id = None
            for r in results:
                if any(kw in r.get("description", "").lower() for kw in author_keywords):
                    entity_id = r["id"]
                    break
            if not entity_id:
                entity_id = results[0]["id"]

            entity_res = requests.get(
                f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json",
                headers=headers, timeout=8
            )
            if not entity_res.content:
                return []
            claims = entity_res.json().get("entities", {}).get(entity_id, {}).get("claims", {})
            qids = []
            for claim in claims.get("P27", []):
                mainsnak = claim.get("mainsnak", {})
                if mainsnak.get("snaktype") == "value":
                    qid = mainsnak.get("datavalue", {}).get("value", {}).get("id")
                    if qid:
                        qids.append(qid)
            return qids
        except:
            return []
    return cached_get(cache_key, fetch)

# ---------------------------
# NORMALIZATION
# ---------------------------

def normalize_genres(raw_genres):
    # Genre normalization removed — we only use nationality shelves now.
    return set()

def nationality_shelves(qids):
    return {COUNTRY_SHELF_MAP[q] for q in qids if q in COUNTRY_SHELF_MAP}

# ---------------------------
# PROCESSING
# ---------------------------

def process_books(df, email, progress_bar, status_text):
    new_shelves = []
    total = len(df)

    for idx, row in df.iterrows():
        title = str(row.get("Title", "")).strip()
        author = str(row.get("Author", "")).strip()
        existing = str(row.get("Bookshelves", ""))

        status_text.markdown(f"**Processing:** {title} — *{author}*")
        progress_bar.progress((idx + 1) / total)

        shelves = set()

        if existing and existing.lower() != "nan":
            for s in existing.split(","):
                s = s.strip()
                if s:
                    shelves.add(s)

        # Prefer ISBN when available for more accurate matches
        isbn = None
        for col in ("ISBN13", "ISBN"):
            raw = str(row.get(col, "")).strip()
            if raw and raw.lower() != "nan":
                cleaned = re.sub(r"[^0-9Xx]", "", raw)
                if cleaned:
                    isbn = cleaned
                    break

        # Book-level genre lookup removed; only nationality shelves applied.

        qids = get_wikidata_nationality(author, email)
        shelves.update(nationality_shelves(qids))

        shelves = {
            re.sub(r"\s+", "-", s.strip().lower())
            for s in shelves if s and s.lower() != "nan"
        }

        new_shelves.append(", ".join(sorted(shelves)))
        time.sleep(0.4)

    df = df.copy()
    df["Bookshelves"] = new_shelves
    return df


# ---------------------------
# UI
# ---------------------------

st.markdown("# 📚 Goodreads Shelf Updater")
st.markdown(
    "Automatically tag your Goodreads library with **author nationality** shelves — using free public APIs, no manual work required."
)

st.divider()

# Step 1 — Email
st.markdown("### Step 1 — Your email address")
st.markdown(
    "Used only to identify your requests to the Wikidata API (their policy requires it). "
    "It is never stored or shared."
)
email = st.text_input("Email address", placeholder="you@example.com")

st.divider()

# Step 2 — Upload
st.markdown("### Step 2 — Upload your Goodreads export")
st.markdown(
    "In Goodreads: go to **My Books → Import and Export → Export Library**. "
    "Then upload the downloaded CSV file here."
)
uploaded_file = st.file_uploader("Choose your Goodreads CSV export", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    book_count = len(df)
    est_minutes = round((book_count * 0.4) / 60)

    st.success(f"✅ {book_count} books loaded.")

    st.info(
        f"⏱ **Heads up:** processing {book_count} books will take roughly "
        f"**{est_minutes}–{est_minutes + 2} minutes** — each book performs one Wikidata lookup (author nationality)."
    )

    st.divider()

    # Step 3 — Run
    st.markdown("### Step 3 — Run")

    if not email or "@" not in email:
        st.warning("Please enter a valid email address above before running.")
    else:
        if st.button("✨ Update my shelves", use_container_width=True, type="primary"):

            st.divider()
            st.markdown("### Processing your library...")

            progress_bar = st.progress(0)
            status_text = st.empty()

            result_df = process_books(df, email, progress_bar, status_text)

            status_text.markdown("**Done!** 🎉")
            progress_bar.progress(1.0)

            # Stats
            all_shelves = [s for row in result_df["Bookshelves"] for s in row.split(", ") if s]
            unique_shelves = set(all_shelves)
            avg_per_book = round(len(all_shelves) / book_count, 1)

            st.divider()
            st.markdown("### Results")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-number">{book_count}</div>
                        <div class="stat-label">Books processed</div>
                    </div>""", unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-number">{len(unique_shelves)}</div>
                        <div class="stat-label">Unique shelves created</div>
                    </div>""", unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-number">{avg_per_book}</div>
                        <div class="stat-label">Avg shelves per book</div>
                    </div>""", unsafe_allow_html=True)

            # Shelf tag cloud
            st.markdown(" ")
            from collections import Counter
            shelf_counts = Counter(all_shelves)
            top_shelves = shelf_counts.most_common(30)
            tags_html = " ".join(
                f'<span class="shelf-tag">{s} <span style="opacity:0.5">·{c}</span></span>'
                for s, c in top_shelves
            )
            st.markdown(f"**Top shelves assigned:**")
            st.markdown(tags_html, unsafe_allow_html=True)

            st.divider()

            # Download
            st.markdown("### Step 4 — Download and import back to Goodreads")
            st.markdown(
                "Download the file below, then go to **Goodreads → My Books → "
                "Import and Export → Import** and upload it. "
                "Your ratings and reviews are untouched — only shelves are updated."
            )

            csv_buffer = io.BytesIO()
            result_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)

            st.download_button(
                label="⬇️ Download goodreads_cleaned.csv",
                data=csv_buffer,
                file_name="goodreads_cleaned.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary",
            )
