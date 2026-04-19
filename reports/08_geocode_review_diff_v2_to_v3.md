# Diff — v2 → v3 Geocode Classification

## Bucket counts (v2 vs v3)

| Bucket | v2 | v3 | Δ |
|--------|---:|---:|--:|
| `auto_accept` | 1,400 | 1,441 | +41 |
| `watchlist` | 29 | 29 | 0 |
| `retry_queue` | 812 | 787 | -25 |
| `manual_review_high_risk` | 30 | 14 | -16 |

## Transition matrix

Rows = v2 bucket; columns = v3 bucket.

| v2 \ v3 | `auto_accept` | `watchlist` | `retry_queue` | `manual_review_high_risk` |
|---------|----:|----:|----:|----:|
| `auto_accept` | 1399 | 0 | 1 | 0 |
| `watchlist` | 0 | 29 | 0 | 0 |
| `retry_queue` | 34 | 0 | 778 | 0 |
| `manual_review_high_risk` | 8 | 0 | 8 | 14 |
| `unseen` | 0 | 0 | 0 | 0 |

## Rows removed from high-risk — false-positive UF parsing (14)

These rows were high-risk in v2 because v2's UF detection matched a state name inside a street/municipality/unit substring. v3's strict end-pattern parser no longer infers a UF for these, so the mismatch signal does not fire.

| row_id | Source UF | v2 inferred UF (substring) | v3 strict UF | formatted_address |
|--------|-----------|---------------------------|--------------|-------------------|
| `BA_0161` | BA | `PA` | `—` | R. Clemente Mariani, 82 - Morpará, BA, 47580-000, Brasil |
| `BA_0173` | BA | `PA` | `—` | R. Herculano C. Martins, s/n - Paramirim, BA, 46190-000, Brasil |
| `BA_0174` | BA | `PA` | `—` | Av. Centenário, 147 - Paramirim, BA, 46190-000, Brasil |
| `BA_0175` | BA | `PA` | `—` | Av. Dr. Manoel Novaes - Paratinga, BA, 47500-000, Brasil |
| `GO_0045` | GO | `TO` | `—` | Rua Tocantins, 7 - Itapaci, GO, 76360-000, Brasil |
| `MG_0231` | MG | `PA` | `—` | R. Ver. José Augusto da Silva, 98 - Rio Paranaíba, MG, 38810-000, Bras |
| `MG_0256` | MG | `PA` | `—` | R. Sebastião Costa Pereira - São João do Paraíso, MG, 39540-000, Brasi |
| `MT_0087` | MT | `ES` | `—` | R. Espírito Santo - Salto do Céu, MT, 78270-000, Brasil |
| `PR_0120` | PR | `AL` | `—` | R. Alagoas, 305 - Nova Aurora, PR, 85410-000, Brasil |
| `PR_0146` | PR | `AM` | `—` | R. Manoel Ribas, 85 - Porto Amazonas, PR, 84140-000, Brasil |
| `RO_0038` | RO | `PA` | `—` | Vale do Paraíso, RO, 76923-000, Brasil |
| `SP_0133` | SP | `PA` | `—` | Av. Zil Brasil, 296 - Mirante do Paranapanema, SP, 19260-000, Brasil |
| `SP_0153` | SP | `PA` | `—` | Paraibuna, SP, 12260-000, Brasil |
| `TO_0007` | TO | `PA` | `—` | Avenida Paranã km 01, S/N - Arraias, TO, 77015-202, Brasil |

## Rows downgraded — special remote/indigenous/military/support units (2)

These rows genuinely have a geocoded UF different from the source UF, but the unit type (UBSI, Polo Base, Pelotão, Missão, DSEI, etc.) means a cross-border placement is expected, so they are demoted to `retry_queue` or `watchlist` rather than high-risk.

| row_id | Unit | Source UF → Geocoded UF | v3 bucket |
|--------|------|-------------------------|-----------|
| `AP_0025` | UBSI Missão Tiriyó | AP → `PA` | `retry_queue` |
| `AP_0026` | UBSI Kuxaré | AP → `PA` | `retry_queue` |

## Rows still truly high-risk in v3 (14)

| row_id | Source UF → Geocoded UF | special | reasons |
|--------|-------------------------|---------|---------|
| `AM_0075` | AM → `—` | yes | formatted_address ends with non-Brazil country (Colômbia) |
| `BA_0139` | BA → `—` |  | coordinates outside Brazil |
| `BA_0199` | BA → `RJ` |  | geocoded_state_abbr=RJ differs from source_state_abbr=BA (standard hospital-type unit) |
| `BA_0219` | BA → `SP` |  | geocoded_state_abbr=SP differs from source_state_abbr=BA (standard hospital-type unit) |
| `MA_0135` | MA → `RJ` |  | geocoded_state_abbr=RJ differs from source_state_abbr=MA (standard hospital-type unit) |
| `MT_0043` | MT → `MT` |  | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0048` | MT → `MT` |  | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0053` | MT → `MT` |  | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0091` | MT → `SC` |  | geocoded_state_abbr=SC differs from source_state_abbr=MT (standard hospital-type unit) |
| `PA_0103` | PA → `RS` |  | geocoded_state_abbr=RS differs from source_state_abbr=PA (standard hospital-type unit) |
| `PE_0009` | PE → `SC` |  | geocoded_state_abbr=SC differs from source_state_abbr=PE (standard hospital-type unit) |
| `PR_0031` | PR → `RS` |  | geocoded_state_abbr=RS differs from source_state_abbr=PR (standard hospital-type unit) |
| `PR_0139` | PR → `RS` |  | geocoded_state_abbr=RS differs from source_state_abbr=PR (standard hospital-type unit) |
| `RR_0034` | RR → `PR` |  | geocoded_state_abbr=PR differs from source_state_abbr=RR (standard hospital-type unit) |

## Parser confirmation

- v3 uses the regex ``-\s*([A-Z]{2})(?=\s*(?:,|$))`` (rightmost match) to extract `geocoded_state_abbr` from `formatted_address`.
- **Substring-based UF parsing has been removed.** Street names, municipality names, neighborhood names, and hospital names are no longer searched for full state names; the v2 substring-fallback branch is kept in the codebase only to reconstruct v2's decision for this diff.
- `source_state_abbr` (derived from the PDF/JSON filename stem) remains the ground-truth context for every row.
