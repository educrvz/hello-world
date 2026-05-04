# Google Sheets Export Summary

Generated from the final patched master after committed manual-triage decisions.

## Files produced

| Tab | CSV path | Rows |
|-----|----------|-----:|
| `publish_ready` | [`build/google_sheets_publish_ready_v1.csv`](../build/google_sheets_publish_ready_v1.csv) | 1,587 |
| `review_queue`  | [`build/google_sheets_review_queue_v1.csv`](../build/google_sheets_review_queue_v1.csv)   | 684 |

Both files:
- UTF-8 encoded, CRLF line endings via Python's `csv` module.
- Accents preserved.
- `antivenoms_raw` flattened from pipe-joined (`A|B|C`) to comma-joined (`A, B, C`) for readability.
- Empty/null-like values exported as blank cells.

## Row-level invariants verified

- `publish_ready_v1.csv` is derived from `final_status = publish_ready` in the final master.
- `review_queue_v1.csv` is derived from watchlist, retry_queue, and manual external-review rows in the final master.
- Google Sheets exports have the same `row_id` sets as their source queues.

## Review queue composition

| final_status | Rows |
|--------------|-----:|
| `retry_queue` | 655 |
| `watchlist` | 29 |
| `manual_review_pending_external` | 0 |
| **Total** | **684** |
