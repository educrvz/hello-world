# Google Sheets Export Summary

## Files produced

| Tab | CSV path | Rows |
|-----|----------|-----:|
| `publish_ready` | [`build/google_sheets_publish_ready_v1.csv`](../build/google_sheets_publish_ready_v1.csv) | 1,446 |
| `review_queue`  | [`build/google_sheets_review_queue_v1.csv`](../build/google_sheets_review_queue_v1.csv)   | 825 |

Both files:
- UTF-8 encoded, no BOM, CRLF line endings via Python's `csv` default.
- Accents preserved.
- 23 columns in the exact order specified:
  `row_id, source_state_abbr, state, municipality, health_unit_name, address, phones_raw, cnes, antivenoms_raw, geocode_query, formatted_address, lat, lng, place_id, partial_match, location_type, geocode_status, final_status, repair_applied, repair_source, repair_outcome, review_status, review_reasons`.
- `antivenoms_raw` flattened from pipe-joined (`A|B|C`) to comma-joined (`A, B, C`) for readability.
- Empty values exported as blank cells (no literal `null` / `None`).
- `lat` / `lng` are plain decimal strings — Google Sheets will parse them as numbers on import.

## Row-level invariants verified

- `google_sheets_publish_ready_v1.csv`: every row has `final_status = publish_ready`. No watchlist, retry_queue, or manual_review_pending_external rows are present.
- `google_sheets_review_queue_v1.csv`: contains 795 `retry_queue`, 29 `watchlist`, and 1 `manual_review_pending_external` rows — no `publish_ready` rows.
- **`PR_0031` appears only in the review queue** (`final_status = manual_review_pending_external`); it is not in the publish-ready export.

## Google Sheets automation

### First attempt — native Python client (not available)
- `gspread`, `googleapiclient`, `google-auth` Python packages → not installed.
- `GOOGLE_APPLICATION_CREDENTIALS` / `GOOGLE_SHEETS_CREDENTIALS` env vars → not set.
- `gcloud` CLI → not installed.
- `~/.config/gspread/`, `~/.gspread/credentials.json` → missing.
- macOS Keychain entries for service account or OAuth token → missing.

### Second attempt — Google Drive MCP tools (partial access, not sufficient)

The Drive MCP server (`search_files`, `create_file`, `read_file_content`, …) is
connected. Probed for existing copies of the two CSVs in Drive — **none found**:

- Query `title contains 'google_sheets_publish_ready_v1' or title contains 'google_sheets_review_queue_v1'` → empty.
- Query `title contains 'publish_ready' or title contains 'review_queue' or title contains 'Hospitais de Referência'` → empty.
- Query `title contains 'geocod' or title contains 'hospitais' or title contains 'antiveneno'` → empty.

The CSVs currently exist only on the local filesystem at `build/`.

#### Why the Drive MCP path still doesn't complete the task

The available Drive tools are file-level only. None of the following Sheets-API
operations can be performed with them:

- Create a single spreadsheet with **two named tabs** (`publish_ready`, `review_queue`).
  `create_file` produces one sheet with a default `Sheet1` tab; there is no
  API for adding, renaming, or listing internal tabs.
- Freeze row 1 on each tab (no range/format API).
- Enable filters on each tab (no filter API).
- Set `row_id` / `cnes` columns to plain-text format (no column-format API).

Additionally, `create_file` accepts only inline base64 `content`, and the two
CSVs are 772 KB and 461 KB respectively (1.03 MB and 615 KB after base64).
Piping ~1.6 MB of base64 through tool parameters is impractical in-session.

### Current outcome

- CSVs remain the deliverable. They are correctly shaped for manual or later
  scripted import.
- The manual import path — [`reports/10_google_sheets_import_guide.md`](10_google_sheets_import_guide.md) —
  produces a sheet that satisfies every requirement (two tabs, frozen header,
  filters, text columns) in roughly 3 minutes of clicking.
- For future automation, the minimal unblock is one of:
  (a) install `gspread` + provide a service-account JSON, or
  (b) add the Google Sheets MCP server (not Drive) so tabs and ranges are
      addressable.

**Sheet URL:** _pending — blocked on either Sheets credentials or a Sheets-level MCP; Drive-only tools are not sufficient. The CSVs are ready for manual import whenever convenient._
