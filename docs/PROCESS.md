# SoroJ — Data Refresh Process

This is the runbook for refreshing the SoroJ antivenom-hospital dataset from
source PDFs to the file served by the live app. One pass, ~15 minutes of
click-and-verify work plus Google geocoding time (roughly 8 minutes for a
full 2,271-row cold run; seconds on a warm resume).

## TL;DR

```bash
# 0. make sure the Google Maps key is in Keychain once:
security add-generic-password -s google_maps_api_key -a "$USER" -w '<key>'

# 1. check if any state PDFs have new versions on gov.br:
python3 scripts/check_updates.py

# 2. if any UF is newer, download the new PDF into `Docs Estado/` and
#    re-extract that one state to `extracted/{UF}.json` using Claude Code
#    multimodal (see §3 below).

# 3. run the rest of the pipeline end-to-end:
./scripts/refresh_dataset.sh

# 4. git diff, commit, push.  Vercel auto-deploys.
```

If nothing upstream changed, step 3 still works — it's resume-safe, skips
already-geocoded rows, and reproduces `app/hospitals.json` deterministically.

## Pipeline at a glance

```
gov.br PESA PDFs
      │  [stage 1] check_updates.py
      ▼
Docs Estado/{UF}_YYYYMMDD.pdf
      │  [stage 2] human drops new PDF into folder
      │  [stage 3] Claude Code multimodal → extracted/{UF}.json
      ▼
extracted/{UF}.json  (27 files, one per state)
      │  [stage 4]  merge_state_jsons.py
      ▼
build/master_raw.{csv,jsonl}
      │  [stage 5]  normalize_hospital_rows.py
      ▼
build/master_normalized.csv
      │  [stage 6]  pre_geocode_qaqc.py
      ▼
(review CSVs + stage-05 report)
      │  [stage 7]  geocode_hospitals.py  (Google Maps, resume-safe)
      ▼
build/master_geocoded.csv  +  build/geocode_raw_responses.jsonl
      │  [stage 8]  classify_geocode_quality_v3.py
      ▼
build/geocode_auto_accept_v3.csv
build/geocode_watchlist_v3.csv
build/geocode_retry_queue_v3.csv
build/geocode_manual_review_high_risk_v3.csv
      │  [stage 9a] exception-queue packaging (inlined in refresh_dataset.sh)
      │  [stage 9b] repair_high_risk_geocodes.py
      │  [stage 9c] apply_repairs.py
      │  [stage 9d] repair_muni_mismatch.py  (salvages retry_queue hide_muni_mismatch rows)
      │  [stage 9e] classify_geocode_quality_v3.py + apply_repairs.py  (propagates 9d salvages)
      │  [stage 9f] apply_manual_triage.py  (re-applies committed operator decisions)
      ▼
build/master_geocoded_patched_v1.csv   (includes publish_policy column)
      │  [stage 10] rebuild_final_artifacts.py
      ▼
build/publish_ready_v1.csv
build/review_queue_v1.csv
build/google_sheets_{publish_ready,review_queue}_v1.csv
      │  [stage 11] build_app_hospitals_json.py
      ▼
app/hospitals.json  +  hospitals.json  ←  production contract
      │  [stage 12] rebuild_final_artifacts.py --check
```

Every stage writes a report at `reports/NN_*.md` that you can read
standalone.

---

## 1. Check for upstream PDF updates

```bash
python3 scripts/check_updates.py
```

Scrapes the gov.br PESA listing, compares publication dates against local
filenames, and prints which UFs are stale.

**Stop and investigate if** the script errors out with a network or HTML-
parse failure — gov.br occasionally reshuffles the page layout. Fix the
scraper or do a manual check.

## 2. Download the new PDF(s)

For each stale UF:

1. Open the Ministry of Health PESA page listed by `check_updates.py`.
2. Download the latest antivenom list for that state.
3. Rename to `{UF}_{YYYYMMDD}.pdf` (the publication date).
4. Move into `Docs Estado/`, replacing the old file.

If you keep the old file around (say for diffing), name it
`{UF}_{YYYYMMDD}.archive.pdf` — the pipeline only picks up files matching
the exact `{UF}_{YYYYMMDD}.pdf` pattern.

## 3. Re-extract affected states

The extractor is the only manual stage. It uses Claude Code's multimodal
read to parse the PDF directly into JSON. For each new/updated UF, prompt
Claude Code with something like:

> Re-extract `Docs Estado/BA_20260105.pdf` to `extracted/BA.json`. Follow
> the schema in `extracted/AC.json`: one object per hospital row with keys
> `state, municipality, health_unit_name, address, phones_raw, cnes,
> antivenoms_raw, source_notes`. Preserve source typos, inherited
> municipality cells, and anomalous CNES values; flag each in
> `source_notes`. Use compact one-line JSON per record.

**Stop and investigate if** the extracted JSON has fewer rows than the
prior version — the schema or PDF layout may have shifted. Diff against the
prior file.

Long-term: this stage is the best candidate for automation (pdfplumber or
Gemini OCR). It's tracked as a separate ticket; for now one UF takes ~1
minute of wall clock.

## 4. Merge — `scripts/merge_state_jsons.py`

Consumes: every `extracted/*.json` file.
Produces: `build/master_raw.csv`, `build/master_raw.jsonl`, `reports/03_merge_summary.md`.
Adds: `row_id` (stable `{UF}_{NNNN}`), `source_state_file`, `source_state_abbr`.

**Stop and investigate if** row_ids are no longer unique (they should be) or
the total row count changes unexpectedly between runs for the same inputs.

## 5. Normalize — `scripts/normalize_hospital_rows.py`

Consumes: `build/master_raw.csv`.
Produces: `build/master_normalized.csv`, `reports/04_normalization_summary.md`.

Adds `*_clean` columns, builds `geocode_query`, flags
`needs_review_pre_geocode` for rows where `health_unit_name`, `municipality`,
`state`, or (address AND cnes) are empty.

**Stop and investigate if** more than ~10 rows get `needs_review_pre_geocode`
— that usually means an upstream extraction lost fields.

## 6. Pre-geocode QA — `scripts/pre_geocode_qaqc.py`

Consumes: `build/master_normalized.csv`.
Produces: `build/review_missing_fields.csv`,
`build/review_possible_duplicates.csv`, `reports/05_pre_geocode_qaqc.md`.

Flags rows missing critical fields and three categories of possible
duplicates (same CNES; same name+muni+state; same geocode_query).

**Stop and investigate if** new CNES collisions appear that weren't there
before — they usually point to transcription errors in the new extraction.

## 7. Geocode — `scripts/geocode_hospitals.py`

Consumes: `build/master_normalized.csv`.
Produces: `build/master_geocoded.csv`, `build/geocode_raw_responses.jsonl`,
`reports/06_geocode_smoke_test.md` (when run with `--limit`).

- Reads the Google Maps API key from `GOOGLE_MAPS_API_KEY` env var first,
  then from macOS Keychain (`service=google_maps_api_key, account=$USER`).
- Resume-safe: rows with terminal status (`OK`, `ZERO_RESULTS`,
  `INVALID_REQUEST`, `NOT_ATTEMPTED_EMPTY_QUERY`) are skipped.
- `--limit 50` runs a smoke test; no args does the full pass.
- `--no-resume` re-hits every row (use only if the API key changed or you
  suspect stale responses).

**Stop and investigate if** success rate drops below ~99% — could indicate
a quota issue, a new key with referer restrictions, or a bad batch of
`geocode_query` inputs.

## 8. Classify quality — `scripts/classify_geocode_quality_v3.py`

Consumes: `build/master_geocoded.csv`.
Produces: the four bucket CSVs, `reports/08_geocode_review_summary_v3.md`,
`reports/08_geocode_review_diff_v2_to_v3.md`.

Uses combined evidence (`location_type`, in-Brazil check, state consistency
via strict `-\s*UF` end-pattern parse, municipality-in-FA check, place_id
reuse). `partial_match` alone is not a trigger.

**Stop and investigate if** the `manual_review_high_risk` bucket exceeds ~30
rows — check the diff report for false-positive UF mismatches; a change to
the strict UF parser may be called for.

## 9. Exception, repair, apply

### 9a. Package exception queue (inlined in `refresh_dataset.sh`)

Packages the 14 high-risk rows into `build/high_risk_exception_queue_v1.csv`
with original PDF filenames resolved from `Docs Estado/`.

### 9b. Repair — `scripts/repair_high_risk_geocodes.py`

For each high-risk row, generates up to 5 deterministic candidate queries,
geocodes each, scores them, picks the best. Outcome is one of
`improved_confidently`, `improved_but_still_review`, `unchanged_bad`,
`inconclusive`. Writes `build/high_risk_repair_best_attempts.csv` and
`reports/09b_high_risk_repair_summary.md`.

### 9c. Apply — `scripts/apply_repairs.py`

Applies every `improved_confidently` row to the master dataset, archives
the prior geocode values in `original_*` columns, and assigns a
`final_status` to every row:

- `publish_ready` — auto_accept_v3 or confidently-repaired high-risk
- `watchlist` — watchlist_v3
- `retry_queue` — retry_queue_v3
- `manual_review_pending_external` — high-risk that couldn't be repaired

Also assigns **`publish_policy`** — whether the row is safe enough to ship:

- `publish` — include in `app/hospitals.json`. Covers all `publish_ready`
  rows plus `watchlist` + `retry_queue` where the municipality is present
  in `formatted_address` AND the FA has >2 comma segments.
- `hide_state_only` — FA is just `"State, Brasil"` (pin in middle of state).
- `hide_muni_mismatch` — municipality missing from FA; Google likely
  placed the pin in the wrong city. Feed into stage 9d for repair.
- `hide_external_review` — `manual_review_pending_external`.

Writes `build/master_geocoded_patched_v1.csv`, `build/publish_ready_v1.csv`,
`build/review_queue_v1.csv`, `reports/09c_apply_repairs_summary.md`.

**Stop and investigate if** `manual_review_pending_external` grows. Each
row needs external resolution (typically CNES DATASUS lookup).

### 9d. Salvage muni-mismatch — `scripts/repair_muni_mismatch.py`

Runs the same deterministic candidate-query + score workflow as 9b, but
against every `hide_muni_mismatch` row. Roughly 5 candidates × ~100 rows
= ~500 API calls per refresh, ~2 minutes. Patches `master_geocoded.csv`
in place for every `improved_confidently` outcome.

Writes `build/muni_mismatch_repair_best_attempts.csv` and
`build/muni_mismatch_repair_raw_responses.jsonl`.

### 9e. Re-classify and re-apply

Rerun `classify_geocode_quality_v3.py` and `apply_repairs.py` so the
9d salvages propagate into the v3 buckets and the final `publish_policy`.

### 9f. Re-apply committed manual-triage decisions

Every CSV under [`data/manual_triage/`](../data/manual_triage/) is fed
through [`scripts/apply_manual_triage.py`](../scripts/apply_manual_triage.py).
Those files are the durable record of operator unhides produced by the
`build_muni_triage.py` / `build_pa_triage.py` HTML triage tools. Because
the master CSV is rebuilt from scratch whenever a state PDF changes, this
stage is what keeps those unhides alive across re-ingests. Naming
convention: `{UF}_{YYYY-MM-DD}_{bucket}.csv` (e.g.
`PA_2026-04-20_muni_mismatch.csv`). The applier is idempotent — it
archives `original_*` only on first touch.

## 10. Reconcile final artifacts — `scripts/rebuild_final_artifacts.py`

Regenerates `build/publish_ready_v1.csv`, `build/review_queue_v1.csv`,
`build/google_sheets_publish_ready_v1.csv`,
`build/google_sheets_review_queue_v1.csv`, and
`reports/10_google_sheets_export_summary.md` from the final
`build/master_geocoded_patched_v1.csv` after stage 9f has re-applied
manual triage. This prevents stale pre-triage queue/export rows from
surviving a full refresh.

The Google Sheets exports flatten pipe-separated antivenoms to commas and
convert `null` literals to blank cells. See
[`reports/10_google_sheets_import_guide.md`](../reports/10_google_sheets_import_guide.md)
to drop these into a Google Sheet.

## 11. Build the app contract — `scripts/build_app_hospitals_json.py`

Consumes: `build/master_geocoded_patched_v1.csv`, filtered to rows where
`publish_policy == publish` (set in stage 9c). That's the full publish set —
auto-accept + confidently-repaired + safe watchlist + safe retry.
Produces: `app/hospitals.json` (Vercel serves this) and `hospitals.json` at
the repo root (same file, kept for diff convenience and legacy tooling).

Stage 12 runs `scripts/rebuild_final_artifacts.py --check` after this build.
It verifies that the master, queues, Google Sheets exports, root JSON and app
JSON still agree on row identity/counts and published CNES values.

Field mapping:

| App field       | Source column              | Transform                                                                 |
|-----------------|---------------------------|---------------------------------------------------------------------------|
| `hospital_name` | `health_unit_name`        | trim/collapse whitespace                                                  |
| `state`         | `source_state_abbr`       | 2-letter UF                                                               |
| `state_name`    | `state`                   | title-cased from upper-case source (`ACRE` → `Acre`, `SÃO PAULO` → `São Paulo`) |
| `city`          | `municipality`            | raw                                                                       |
| `lat`, `lng`    | `lat`, `lng`              | `float()`; row dropped if either is blank                                 |
| `address`       | `address`                 | raw                                                                       |
| `antivenoms`    | `antivenoms_raw`          | split on `\|`, drop blanks → string array                                 |
| `phones`        | `phones_raw`              | split on `/` or `,`; drop placeholders (`não disponível`, `sem contato`, `****`, `-`, <4 chars) → string array |
| `source_date`   | `source_state_file`       | ISO `YYYY-MM-DD` parsed from `Docs Estado/{UF}_YYYYMMDD.pdf`              |
| `cnes`          | `cnes`                    | string                                                                    |
| `geocode_tier`  | `location_type`           | `ROOFTOP`→1, `RANGE_INTERPOLATED`→2, `GEOMETRIC_CENTER`→3, `APPROXIMATE`→3; the app renders tier 3 with a leading `~` on the distance |

**Stop and investigate if** the output row count deviates substantially
from the `publish_ready_v1.csv` row count — the only legitimate reason to
drop a row here is blank lat/lng, which should be near zero after stage 9c.

---

## Ship to production

```bash
git status                        # expect app/hospitals.json, hospitals.json, reports/*, build/*
git add app/hospitals.json hospitals.json reports build
git commit -m "data: refresh YYYY-MM-DD using v3 classifier + N repairs"
git push                          # Vercel auto-deploys
```

Verify:

- Load the app at its production URL — confirm the map renders.
- Open the **[SoroJ Feedback](https://www.notion.so/SoroJ-Feedback-345eeae1044a80b99355cb03bd794c15?source=copy_link)**
  Notion page. For each reported bad pin, search for the row in the new
  `hospitals.json` and confirm its coordinates now look right (cross-check
  with Google Maps).
- Spot-check 5 random rows from `publish_ready_v1.csv`.

**Rollback:** `git revert <commit-hash>` + push. Vercel redeploys the prior
`hospitals.json` in ~1 minute.

---

## Fixing a reported bad pin or address

For one-off user reports (wrong pin *or* wrong address on a specific
hospital), you don't need the PDF pipeline. The **SoroJá Overrides** Google
Sheet layers per-`cnes` corrections on top of `hospitals.json`. The override
file at [`data/location_overrides.json`](../data/location_overrides.json) is
the source of truth; the sheet edits it via the GitHub API.

**Per-report workflow (~2 min, no terminal needed):**

1. Open the SoroJá Overrides Google Sheet → tab **Hospitals** → filter by
   name or city.
2. Click **Current pin** (where SoroJá places it today) and **Find correct
   pin** (Google Maps search for the stored address). Compare against the
   reporter's evidence; if the address search shows the correct location,
   right-click the correct pin in Google Maps and copy coordinates.
3. Switch to tab **Overrides** → add a row. Columns:
   - `cnes` (required).
   - `corrected_lat`, `corrected_lng` — supply both or neither. Blank is
     allowed when you only need to fix the address.
   - `corrected_address` — optional free-text street address to display in
     the app. Leave blank if only the pin is wrong.
   - `reason` (required — link the Notion report), `verified_on`.
   - The sheet rejects coords outside Brazil.
4. Menu → **SoroJá → Publish overrides** → confirm. The script commits to
   `main`; Vercel deploys in ~1 min. The row flips to `status = published`.

**How it lands in `hospitals.json`:**

Stage 11 ([`scripts/build_app_hospitals_json.py`](../scripts/build_app_hospitals_json.py))
reads `data/location_overrides.json` at the end of its main loop. For each
override whose `cnes` is in the published set:

- If `lat` **and** `lng` are present, it overwrites both and sets
  `geocode_tier = 1` (manually verified). Supplying only one of them logs a
  WARN and is skipped.
- If `address` is present and non-empty, it overwrites the displayed
  address.
- Unknown `cnes` values log a WARN and are skipped.

A cold `refresh_dataset.sh` run automatically honors overrides — they live
through pipeline refreshes because they apply at the final build stage.

**Rollback a single override:** delete the row in the Overrides tab and
click Publish again. The commit history has the prior state.

**Setup & script source:**
[`scripts/sheet/Code.gs`](../scripts/sheet/Code.gs) holds the Apps Script
paste-in plus setup instructions (required script properties:
`GITHUB_TOKEN` fine-grained PAT with `Contents: read/write`, `GITHUB_REPO`
`educrvz/sos-antiveneno`).

---

## Community notes (additive layer)

Community-sourced relatos that surface "the official Ministry of Health
data is wrong" without mutating any official field. They render as a
distinct amber callout on each hospital card, dated, with the standing
disclaimer *"Informação não confirmada pelo Ministério da Saúde."*

**Source:** the **Community Notes** tab in the same overrides Google Sheet.
One row per relato; multiple rows for the same CNES become an array of
notes on that hospital. Columns:

```
cnes | hospital_name (ref) | category | reported_at | public_summary | expires_at | status | published_at
```

**Allowed categories** (mirrors `docs/community-reports-plan.md`):
`contact_fix`, `pin_fix`, `closed`, `wrong_unit`, `other`.

**Critical invariant:** `public_summary` is **maintainer-authored canned
text**, not raw user input. Keep it factual, ≤280 chars, no PII, no
phone numbers of reporters, no patient details. The Apps Script
validator enforces the length cap; the no-PII discipline is enforced by
convention.

**Publishing flow:** add rows in the Community Notes tab → menu
*SoroJá → Publicar relatos da comunidade* → Apps Script writes
`data/community_notes.json` to GitHub → the rebuild workflow regenerates
`hospitals.json` with notes attached inline → Vercel deploys.

**Build-time behavior:** [`scripts/build_app_hospitals_json.py`](../scripts/build_app_hospitals_json.py)
loads `data/community_notes.json` and attaches active (non-expired)
notes to each hospital record as a `community_notes: [...]` array,
sorted most-recent-first. The official fields (`hospital_name`, `phones`,
`address`, `note`) are never touched by this layer.

**Removing a note:** delete the row in the Community Notes tab and
re-publish, or set its `expires_at` to a past date.

---

## Appendix A — handling the review queue

`build/review_queue_v1.csv` contains 684 rows today:

- **655 `retry_queue`** — Google returned something (often APPROXIMATE) but
  the evidence didn't stack up. Most common fix: hand-pick a better
  `geocode_query` and re-run stage 7 on that one row.
- **29 `watchlist`** — geocoded to neighborhood-level precision, usable but
  worth a second pair of eyes before promoting.

To promote a reviewed row back to `publish_ready`, append its patched row
to `build/master_geocoded_patched_v1.csv` with `final_status = publish_ready`,
then re-run stage 11. (A dedicated promotion script is a future ticket.)

## Appendix B — handling `manual_review_pending_external`

1. Open `build/high_risk_exception_queue_v1.csv` and find the row by
   `row_id`.
2. Use the `cnes` (or the hospital name) to search
   [cnes.datasus.gov.br](http://cnes.datasus.gov.br).
3. Copy the official address from CNES.
4. Construct a manual patch CSV with the corrected lat/lng and
   `final_status = publish_ready`, or just edit `build/master_geocoded.csv`
   directly and re-run from stage 9c.

## Appendix C — the 10-stage report map

| Stage | Report                                                                            |
|-------|-----------------------------------------------------------------------------------|
| 01    | [`reports/01_inventory.md`](../reports/01_inventory.md)                            |
| 02    | [`reports/02_schema_audit.md`](../reports/02_schema_audit.md)                      |
| 03    | [`reports/03_merge_summary.md`](../reports/03_merge_summary.md)                    |
| 04    | [`reports/04_normalization_summary.md`](../reports/04_normalization_summary.md)    |
| 05    | [`reports/05_pre_geocode_qaqc.md`](../reports/05_pre_geocode_qaqc.md)              |
| 06    | [`reports/06_geocode_smoke_test.md`](../reports/06_geocode_smoke_test.md)          |
| 07    | [`reports/07_geocode_full_run.md`](../reports/07_geocode_full_run.md)              |
| 08    | [`reports/08_geocode_review_summary_v3.md`](../reports/08_geocode_review_summary_v3.md) + [`v2 → v3 diff`](../reports/08_geocode_review_diff_v2_to_v3.md) |
| 09a   | [`reports/09a_high_risk_exception_summary.md`](../reports/09a_high_risk_exception_summary.md) + [`09a_high_risk_source_context.md`](../reports/09a_high_risk_source_context.md) |
| 09b   | [`reports/09b_high_risk_repair_summary.md`](../reports/09b_high_risk_repair_summary.md) |
| 09c   | [`reports/09c_apply_repairs_summary.md`](../reports/09c_apply_repairs_summary.md)  |
| 10    | [`reports/10_google_sheets_export_summary.md`](../reports/10_google_sheets_export_summary.md) + [`import guide`](../reports/10_google_sheets_import_guide.md) |
