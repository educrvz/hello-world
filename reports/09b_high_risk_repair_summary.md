# High-Risk Repair Summary

**Input queue:** `build/high_risk_exception_queue_v1.csv`
**Candidates CSV:** `build/high_risk_repair_candidates.csv`
**Best attempts CSV:** `build/high_risk_repair_best_attempts.csv`
**Raw API responses:** `build/high_risk_repair_raw_responses.jsonl`

**Rows processed:** 14
**Candidate queries attempted:** 58

## Counts by `repair_outcome`

| Outcome | Count |
|---------|------:|
| `improved_confidently` | 13 |
| `improved_but_still_review` | 1 |
| `unchanged_bad` | 0 |
| `inconclusive` | 0 |

## All 14 rows — old vs new

| row_id | UF | Muni | Outcome | Δscore | Old FA | Best FA | Best loc_type |
|--------|----|------|---------|-------:|--------|---------|---------------|
| `AM_0075` | AM | São Gabriel da Cachoeira | `improved_confidently` | +285 | Querari, Mitú, Vaupés, Colômbia | São Gabriel da Cachoeira - AM, 69750-000, Brasil | `GEOMETRIC_CENTER` |
| `BA_0139` | BA | Jucuruçu | `improved_confidently` | +595 | Califórnia, EUA | Av. Manoel Rodrigues da Silva, Jucuruçu - BA, 45834-000 | `GEOMETRIC_CENTER` |
| `BA_0199` | BA | Rio Real | `improved_confidently` | +230 | Centro, Rio de Janeiro - RJ, Brasil | R. Afonso Florisvaldo, 709, Rio Real - BA, 48330-000, B | `RANGE_INTERPOLATED` |
| `BA_0219` | BA | Sebastião Laranjeiras | `improved_confidently` | +185 | Centro, Campinas - SP, Brasil | Av. Tiradentes - Sebastião Laranjeiras, BA, 46450-000,  | `GEOMETRIC_CENTER` |
| `MA_0135` | MA | SÃO DOMINGOS DO AZEITÃO | `improved_confidently` | +225 | Centro, Rio de Janeiro - RJ, Brasil | R. Matagal, São Domingos do Azeitão - MA, 65888-000, Br | `GEOMETRIC_CENTER` |
| `MT_0043` | MT | Itiquira | `improved_confidently` | +180 | Centro Norte, Várzea Grande - MT, Brasil | Av. Treze de Maio, 500 - CENTRO, Itiquira - MT, 78790-0 | `ROOFTOP` |
| `MT_0048` | MT | Juruena | `improved_confidently` | +180 | Centro Norte, Várzea Grande - MT, Brasil | Travessa Lucinda Kniess, 20 - Centro, Juruena - MT, 783 | `ROOFTOP` |
| `MT_0053` | MT | Matupá | `improved_confidently` | +110 | Centro Norte, Várzea Grande - MT, Brasil | Matupá - MT, Brasil | `APPROXIMATE` |
| `MT_0091` | MT | São José do Povo | `improved_confidently` | +185 | Centro, São José - SC, Brasil | R. Castelo Branco - São José do Povo, MT, 78773-000, Br | `GEOMETRIC_CENTER` |
| `PA_0103` | PA | Oeiras do Pará | `improved_confidently` | +225 | Santa Maria - RS, Brasil | R. Honório Bastos, Oeiras do Pará - PA, 68470-000, Bras | `GEOMETRIC_CENTER` |
| `PE_0009` | PE | Palmares | `improved_confidently` | +115 | BR-101, KM 185 - Guaporanga, Biguaçu - SC, 88168-400, B | Tv. Agamenon Magalhães - Palmares, PE, 55540-000, Brasi | `GEOMETRIC_CENTER` |
| `PR_0031` | PR | Capitão Leônidas Marques | `improved_but_still_review` | +110 | Cidade Baixa, Porto Alegre - RS, Brasil | Cap. Leônidas Marques, PR, 85790-000, Brasil | `APPROXIMATE` |
| `PR_0139` | PR | Piraí do Sul | `improved_confidently` | +250 | Centro Histórico, Porto Alegre - RS, Brasil | R. Joanino Miléo, 49 - CENTRO, Piraí do Sul - PR, 84240 | `ROOFTOP` |
| `RR_0034` | RR | Pacaraima | `improved_confidently` | +160 | 4°29'11.8"N 61°08'28.1"W - 1, 8, Piraí do Sul - PR, 842 | R. Caribe, Pacaraima - RR, 69345-000, Brasil | `GEOMETRIC_CENTER` |

## Rows still unresolved (1)

| row_id | Outcome | Best score | Best reasons |
|--------|---------|-----------:|--------------|
| `PR_0031` | `improved_but_still_review` | 35 | in_brazil +50; state_unknown; muni_not_in_fa -30; loc_type=APPROXIMATE +5; specific_fa +15; partial+non_rooftop -5 |

## Recommendation

- **13** row(s) are good candidates for a targeted patch of the main dataset (write-through in a follow-up step).
- **1** row(s) remain unresolved by deterministic candidate queries. Recommendation: move them to a tiny external-review batch (CNES DATASUS lookup or state health-department portal) rather than burning more geocode budget — the upside is small and the signal-to-noise is now low.
