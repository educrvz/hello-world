# Google Sheets Import Guide

A short checklist to get the two exports into a single Google Sheet named
**"Hospitais de Referência - Geocoded v1"** with two tabs.

## 1. Create the spreadsheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new blank spreadsheet.
2. Rename it to: `Hospitais de Referência - Geocoded v1`.

## 2. Import the publish-ready tab

1. Rename the default `Sheet1` tab to `publish_ready`.
2. `File` → `Import` → `Upload` → select
   [`build/google_sheets_publish_ready_v1.csv`](../build/google_sheets_publish_ready_v1.csv).
3. In the import dialog:
   - **Import location:** `Replace current sheet`
   - **Separator type:** `Comma`
   - **Convert text to numbers, dates, and formulas:** **UNCHECK this box**.
     This is the only critical setting — leaving it on will corrupt `row_id`
     (e.g. `AC_0001` stays intact but future-proofs against import changes)
     and, more importantly, will strip any future leading zeros on `cnes`.
4. Click `Import data`.

After import, confirm:
- The tab has **1,446 rows** plus a header row.
- Column `row_id` reads values like `AC_0001`, `SP_0242` — left-aligned text.
- Column `cnes` shows full codes like `2816210`, `655`, `26417` — left-aligned text.
- Column `lat` / `lng` are right-aligned numbers.

## 3. Import the review-queue tab

1. Add a new tab: `+` (bottom-left) → rename it to `review_queue`.
2. `File` → `Import` → `Upload` → select
   [`build/google_sheets_review_queue_v1.csv`](../build/google_sheets_review_queue_v1.csv).
3. In the import dialog:
   - **Import location:** `Append to current sheet`? No — choose
     `Replace current sheet`.
   - **Separator type:** `Comma`.
   - **Convert text to numbers, dates, and formulas:** **UNCHECK**.
4. Click `Import data`.

Confirm the tab has **825 rows** plus a header row.

## 4. Freeze headers and format

On each tab:
1. `View` → `Freeze` → `1 row`.
2. Select columns `row_id` and `cnes`, then `Format` → `Number` → `Plain text`.
   This prevents any lat/lng-style auto-formatting if you later paste new
   rows in.

## 5. Usage notes

- **`publish_ready` is the operational dataset** — it is what should feed
  the end-user display (website, app, map). Every row has
  `final_status = publish_ready`.
- **`review_queue` is NOT for end-user display.** It contains 29 `watchlist`
  rows (geocoded to neighborhood-level precision, usable but worth
  verifying), 795 `retry_queue` rows (APPROXIMATE results or municipality
  mismatches worth re-geocoding), and 1 `manual_review_pending_external`
  row (`PR_0031` — needs manual lookup on CNES DATASUS before being
  promoted).
- **`row_id` and `cnes` should remain text.** They look numeric but are
  identifiers; preserving leading zeros and compound tokens (`AC_0001`) is
  essential for later joins back to the source JSON / PDF data.
- **Do not sort without copying first.** Sorting the live tab breaks the
  `row_id` → source-JSON-position relationship documented in
  [`scripts/merge_state_jsons.py`](../scripts/merge_state_jsons.py).
  If you need to sort for review, duplicate the tab first.

## 6. When to regenerate

Regenerate the CSVs (re-run the pipeline) when any of the following change:

- New or updated state PDFs land in `Docs Estado/`.
- A reviewer resolves rows in the `review_queue` tab and you want them
  promoted to `publish_ready`.
- The classifier logic is revised (there is already a v2 → v3 diff in
  [`reports/08_geocode_review_diff_v2_to_v3.md`](08_geocode_review_diff_v2_to_v3.md)).
