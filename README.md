# 📚 Goodreads Shelf Updater

Automatically enrich your Goodreads library shelves using Wikidata — no manual tagging required.

The script takes your Goodreads CSV export and assigns author nationality shelves (e.g. `japanese-literature`, `russian-literature`, `latin-american-fiction`) based on Wikidata facts.

---

## Features

- **Author nationality detection** via Wikidata (P27) — supports modern countries and many historical states
- **Preserves all your existing data** — ratings, reviews, read dates, and existing shelves are never removed
- **Persistent cache** — results are saved to `api_cache.json` so re-runs don't repeat API calls
- **Unmapped QID warnings** — notifies when a Wikidata country QID isn't mapped to a shelf tag
- **Run summary** — shows total shelves assigned and flags any books with no data found

---

## Requirements

```bash
pip install pandas requests
```

Python 3.8 or higher.

---

## Setup

**1. Export your Goodreads library**

Go to Goodreads → My Books → Import and Export → Export Library. Save the file as `goodreads_library_export.csv` in the same folder as the script.

**2. Set your User-Agent / email**

Wikidata requires a descriptive `User-Agent` header. Open the script and find the header string and replace the email with your address:

```python
"User-Agent": "GoodreadsShelfUpdater/1.0 (personal project; your@email.com)"
```

This is only so Wikidata can contact you if your client misbehaves — you don't need to register.

**3. Run the script**

```bash
python goodreads_shelf_updater.py
```

The enriched library is saved to `goodreads_cleaned.csv`.

---

## Output

Your original CSV is preserved exactly, with only the `Bookshelves` column updated. Example of what gets added:

| Title | Author | Bookshelves (before) | Bookshelves (after) |
|---|---|---|---|
| Crime and Punishment | Fyodor Dostoevsky | read | classics, literary-fiction, psychological-fiction, read, russian-literature |
| Snow Country | Yasunari Kawabata | to-read | japanese-literature, literary-fiction, to-read |
| One Hundred Years of Solitude | Gabriel García Márquez | read | classics, latin-american-fiction, literary-fiction, magical-realism, read |

---

## How It Works

For each book the script:

1. Keeps all your existing shelves
2. Queries **Wikidata** for the author's country of citizenship (P27)
3. Maps Wikidata country QIDs to hyphenated shelf tags using `COUNTRY_SHELF_MAP`
4. Merges, deduplicates, and sorts everything alphabetically

All API results and derived selections are cached in `api_cache.json`. Delete this file to force fresh lookups.

---

## Extending the Script

**Adding a new nationality:**

Find the author's country on [Wikidata](https://www.wikidata.org) and note the QID (the `Q` number in the URL). Add it to `COUNTRY_SHELF_MAP` in the script:

```python
"Q928": "southeast-asian-fiction",   # Philippines
```

**(Genre mapping removed)**

The script no longer derives book-level genres. Only nationality shelves are assigned.

---

## Importing Back to Goodreads

Once the script has finished, you can import `goodreads_cleaned.csv` directly back into Goodreads:

1. Go to **Goodreads → My Books → Import and Export**
2. Under **Import**, click **Choose File** and select `goodreads_cleaned.csv`
3. Click **Import**

Goodreads matches books by ISBN, so existing ratings, reviews, and read dates are preserved — only shelf assignments change.

> **Note:** Goodreads' importer can be slow on large libraries and occasionally silently skips rows. If shelves don't appear after importing, wait a few minutes and refresh. If issues persist, try splitting the CSV into smaller batches of ~200 rows.

---

## Limitations

- Genre detection quality now depends on Wikidata coverage for works/editions (P136). Some editions may not have P136 statements and will not receive a derived genre.
- Some authors are listed under historical states on Wikidata (e.g. Tolstoy under Russian Empire rather than Russia). The script handles many common cases but you may occasionally see `Unmapped Wikidata QID` warnings for obscure entities.

---

## APIs Used

| API | Used For | Key Required |
|---|---|---|
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Data_access) | Author nationality (P27) | No |

Wikidata requires a descriptive `User-Agent` header but no API key.

---

## License

MIT — do whatever you like with it.
