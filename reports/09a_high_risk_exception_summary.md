# High-Risk Exception Queue — Summary

**Input:** `build/geocode_manual_review_high_risk_v3.csv`
**Exception CSV:** `build/high_risk_exception_queue_v1.csv`
**Context report:** `reports/09a_high_risk_source_context.md`
**Total high-risk rows:** 14

## Counts by reason type

_A row may appear in more than one category._

| Reason | Count |
|--------|------:|
| `non_brazil_country` | 1 |
| `out_of_brazil_coords` | 1 |
| `state_mismatch` | 9 |
| `place_id_reuse` | 3 |
| `other` | 0 |

## Rows grouped by source state

| source_state_abbr | rows |
|-------------------|------|
| AM | AM_0075 |
| BA | BA_0139, BA_0199, BA_0219 |
| MA | MA_0135 |
| MT | MT_0043, MT_0048, MT_0053, MT_0091 |
| PA | PA_0103 |
| PE | PE_0009 |
| PR | PR_0031, PR_0139 |
| RR | RR_0034 |

## Rows with non-Brazil country in `formatted_address`

| row_id | Source muni, UF | formatted_address | reasons |
|--------|-----------------|-------------------|---------|
| `AM_0075` | São Gabriel da Cachoeira, AM | Querari, Mitú, Vaupés, Colômbia | formatted_address ends with non-Brazil country (Colômbia) |

## Rows with coordinates outside Brazil

| row_id | Source muni, UF | formatted_address | reasons |
|--------|-----------------|-------------------|---------|
| `BA_0139` | Jucuruçu, BA | Califórnia, EUA | coordinates outside Brazil |

## Rows with confirmed UF mismatch (strict parser)

| row_id | Source muni, UF | formatted_address | reasons |
|--------|-----------------|-------------------|---------|
| `BA_0199` | Rio Real, BA | Centro, Rio de Janeiro - RJ, Brasil | geocoded_state_abbr=RJ differs from source_state_abbr=BA (standard hospital-type unit) |
| `BA_0219` | Sebastião Laranjeiras, BA | Centro, Campinas - SP, Brasil | geocoded_state_abbr=SP differs from source_state_abbr=BA (standard hospital-type unit) |
| `MA_0135` | SÃO DOMINGOS DO AZEITÃO, MA | Centro, Rio de Janeiro - RJ, Brasil | geocoded_state_abbr=RJ differs from source_state_abbr=MA (standard hospital-type unit) |
| `MT_0091` | São José do Povo, MT | Centro, São José - SC, Brasil | geocoded_state_abbr=SC differs from source_state_abbr=MT (standard hospital-type unit) |
| `PA_0103` | Oeiras do Pará, PA | Santa Maria - RS, Brasil | geocoded_state_abbr=RS differs from source_state_abbr=PA (standard hospital-type unit) |
| `PE_0009` | Palmares, PE | BR-101, KM 185 - Guaporanga, Biguaçu - SC, 88168-400, Brasil | geocoded_state_abbr=SC differs from source_state_abbr=PE (standard hospital-type unit) |
| `PR_0031` | Capitão Leônidas Marques, PR | Cidade Baixa, Porto Alegre - RS, Brasil | geocoded_state_abbr=RS differs from source_state_abbr=PR (standard hospital-type unit) |
| `PR_0139` | Piraí do Sul, PR | Centro Histórico, Porto Alegre - RS, Brasil | geocoded_state_abbr=RS differs from source_state_abbr=PR (standard hospital-type unit) |
| `RR_0034` | Pacaraima, RR | 4°29'11.8"N 61°08'28.1"W - 1, 8, Piraí do Sul - PR, 84240-000, Brasil | geocoded_state_abbr=PR differs from source_state_abbr=RR (standard hospital-type unit) |

## Rows with `place_id` reuse across unrelated municipalities

| row_id | Source muni, UF | formatted_address | reasons |
|--------|-----------------|-------------------|---------|
| `MT_0043` | Itiquira, MT | Centro Norte, Várzea Grande - MT, Brasil | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0048` | Juruena, MT | Centro Norte, Várzea Grande - MT, Brasil | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0053` | Matupá, MT | Centro Norte, Várzea Grande - MT, Brasil | place_id reused across multiple unrelated (municipality, state) pairs |
