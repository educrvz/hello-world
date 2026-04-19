# Schema Audit Report — `extracted/`

**Folder:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/extracted/`
**Files audited:** 27
**Total records audited:** 2,271

## 1. Top-level structure

Every file is expected to be a JSON array of record objects.

| File | Top-level type | OK? |
|------|----------------|-----|
| AC.json | `list` | yes |
| AL.json | `list` | yes |
| AM.json | `list` | yes |
| AP.json | `list` | yes |
| BA.json | `list` | yes |
| CE.json | `list` | yes |
| DF.json | `list` | yes |
| ES.json | `list` | yes |
| GO.json | `list` | yes |
| MA.json | `list` | yes |
| MG.json | `list` | yes |
| MS.json | `list` | yes |
| MT.json | `list` | yes |
| PA.json | `list` | yes |
| PB.json | `list` | yes |
| PE.json | `list` | yes |
| PI.json | `list` | yes |
| PR.json | `list` | yes |
| RJ.json | `list` | yes |
| RN.json | `list` | yes |
| RO.json | `list` | yes |
| RR.json | `list` | yes |
| RS.json | `list` | yes |
| SC.json | `list` | yes |
| SE.json | `list` | yes |
| SP.json | `list` | yes |
| TO.json | `list` | yes |

## 2. Keys in a normal record

Sample (AC.json, record 0):

```json
{
  "state": "ACRE",
  "municipality": "Acrelândia",
  "health_unit_name": "Unidade Mista de Saúde de Acrelândia",
  "address": "Avenida Paraná, 346 – Centro",
  "phones_raw": "(68) 3235-1188",
  "cnes": "5701929",
  "antivenoms_raw": [
    "Botrópico",
    "Fonêutrico",
    "Loxoscélico",
    "Escorpiônico"
  ],
  "source_notes": null
}
```

Expected key set (8 keys):

- `state`
- `municipality`
- `health_unit_name`
- `address`
- `phones_raw`
- `cnes`
- `antivenoms_raw`
- `source_notes`

## 3. Key presence per file

A `✓` means **every** record in that file contains the key.

| File | state | municipality | health_unit_name | address | phones_raw | cnes | antivenoms_raw | source_notes | extras |
|------|-----|-----|-----|-----|-----|-----|-----|-----|--------|
| AC.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| AL.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| AM.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| AP.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| BA.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| CE.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| DF.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| ES.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| GO.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| MA.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| MG.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| MS.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| MT.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| PA.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| PB.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| PE.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| PI.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| PR.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| RJ.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| RN.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| RO.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| RR.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| RS.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| SC.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| SE.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| SP.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| TO.json | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |

## 4. Null-value frequency

Count of records where a key is present but its value is `null`. Values that are empty strings are not counted here.

| Key | Non-null records | Null records | % null |
|-----|-----------------:|-------------:|-------:|
| `state` | 2,271 | 0 | 0.0% |
| `municipality` | 2,271 | 0 | 0.0% |
| `health_unit_name` | 2,271 | 0 | 0.0% |
| `address` | 2,263 | 8 | 0.4% |
| `phones_raw` | 2,097 | 174 | 7.7% |
| `cnes` | 2,260 | 11 | 0.5% |
| `antivenoms_raw` | 2,271 | 0 | 0.0% |
| `source_notes` | 483 | 1,788 | 78.7% |

## 5. Schema inconsistencies

- **PA.json** — empty antivenoms_raw arrays: 1
- **PR.json** — empty antivenoms_raw arrays: 6
- **RO.json** — empty antivenoms_raw arrays: 2

## 6. Recommended canonical schema for the merged dataset

The current 8-key schema is sound. For the merged dataset we recommend keeping the same keys, tightening types slightly, and adding an auto-generated ID.

```jsonc
{
  "id":              "string   (required) — slug like `SP-sao-paulo-hospital-vital-brazil-2091356`; stable primary key across re-runs",
  "state":           "string   (required) — uppercase full state name, e.g. \"SÃO PAULO\"",
  "state_code":      "string   (required) — 2-letter UF code, e.g. \"SP\"; derived from source filename",
  "municipality":    "string   (required) — as written in source; casing preserved",
  "health_unit_name":"string   (required) — as written in source",
  "address":         "string | null — raw address string, may be null when source cell is blank",
  "phones_raw":      "string | null — untouched phone text; normalized phones go in a separate field when added later",
  "cnes":            "string | null — 7-digit CNES code preferred; shorter values preserved verbatim and flagged in source_notes",
  "antivenoms_raw":  "string[] (required, may be empty) — each element is one antivenom name as written in source, order preserved",
  "source_notes":    "string | null — free-text notes about source anomalies (typos, merged cells, missing fields)"
}
```

### Rules to adopt during merge

1. **Required, never null:** `id`, `state`, `state_code`, `municipality`, `health_unit_name`, `antivenoms_raw`.
2. **Nullable:** `address`, `phones_raw`, `cnes`, `source_notes`. Use `null`, never empty string.
3. **`antivenoms_raw`** is always an array; use `[]` for truly unknown rather than `null`.
4. **`cnes`** stored as string to preserve leading zeros and sub-7-digit values; validate length and flag in `source_notes` when < 7 digits.
5. Source-preservation principle stays in force: typos, duplicates, and mixed casing from the source are kept verbatim; all deviations are recorded in `source_notes`.
6. A follow-up normalization pass (phones, antivenom canonical names, geocoded address) should write **new** fields (`phones`, `antivenoms`, `lat`, `lng`) and leave the `*_raw` fields untouched.
