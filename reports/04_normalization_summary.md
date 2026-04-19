# Normalization Summary

**Input:**  `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/master_raw.csv`
**Output:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/master_normalized.csv`

**Total rows processed:** 2,271
**Rows flagged `needs_review_pre_geocode = true`:** 4
**Flag rate:** 0.18%

## Flag reasons

A row can match multiple reasons; each reason counts once per matching row.

| Reason | Rows |
|--------|-----:|
| `health_unit_name empty` | 0 |
| `municipality empty` | 0 |
| `state empty` | 0 |
| `address and cnes both empty` | 4 |

## Flagged rows by state

| State | Flagged / Total |
|-------|----------------:|
| PA | 2 / 172 |
| RO | 1 / 39 |
| SP | 1 / 242 |

## All normalization notes (informational)

Not every note is a blocker — e.g. `phones empty` is common and acceptable.

| Note | Rows |
|------|-----:|
| phones empty | 174 |
| antivenoms empty | 9 |
| address and cnes both empty | 4 |
| address empty | 4 |

## Rules applied

- Trim leading/trailing whitespace; collapse all internal whitespace (spaces, tabs, newlines) to a single space.
- Preserve accents; no case transformations.
- Keep `cnes` as string in original column; no `cnes_clean` is created.
- Original raw columns are never overwritten; only new `*_clean` and derived columns are added.
- `phones_clean`: whitespace-cleaned copy of `phones_raw`; all punctuation preserved.
- `antivenoms_joined`: pipe-split the CSV `antivenoms_raw`, trim each, drop blanks, rejoin with `, `. Source order and duplicates are preserved.
- `geocode_query`: `health_unit_name_clean, address_clean, municipality_clean, state_clean, Brasil` joined by `, `, with empty parts skipped to avoid doubled commas.
- `needs_review_pre_geocode = true` when `health_unit_name`, `municipality`, or `state` is empty, or when `address` AND `cnes` are both empty.
