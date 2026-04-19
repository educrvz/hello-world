# Apply Repairs — Summary

**Patched master:** `build/master_geocoded_patched_v1.csv`
**Publish-ready:** `build/publish_ready_v1.csv`
**Review queue:**  `build/review_queue_v1.csv`

## Totals

- **Rows in patched master:** 2,271
- **Repairs applied:** 13

## `final_status` distribution

| final_status | Rows |
|--------------|-----:|
| `publish_ready` | 1,454 |
| `watchlist` | 29 |
| `retry_queue` | 787 |
| `manual_review_pending_external` | 1 |
| **Total** | **2,271** |

## `publish_policy` distribution

| publish_policy | Rows |
|----------------|-----:|
| `publish` | 2,137 |
| `hide_state_only` | 34 |
| `hide_muni_mismatch` | 99 |
| `hide_external_review` | 1 |
| `hide_unknown` | 0 |
| **Total ready for hospitals.json** | **2,137** |

## PR_0031 status

- `repair_applied = false`
- `final_status = manual_review_pending_external`
- `repair_outcome = improved_but_still_review`

## 13 repaired rows — old vs new (13 applied)

| row_id | old formatted_address | new formatted_address | old location_type | new location_type |
|--------|-----------------------|-----------------------|-------------------|-------------------|
| `AM_0075` | Querari, Mitú, Vaupés, Colômbia | São Gabriel da Cachoeira - AM, 69750-000, Brasil | `APPROXIMATE` | `GEOMETRIC_CENTER` |
| `BA_0139` | Califórnia, EUA | Av. Manoel Rodrigues da Silva, Jucuruçu - BA, 45834-000 | `APPROXIMATE` | `GEOMETRIC_CENTER` |
| `BA_0199` | Centro, Rio de Janeiro - RJ, Brasil | R. Afonso Florisvaldo, 709, Rio Real - BA, 48330-000, B | `APPROXIMATE` | `RANGE_INTERPOLATED` |
| `BA_0219` | Centro, Campinas - SP, Brasil | Av. Tiradentes - Sebastião Laranjeiras, BA, 46450-000,  | `APPROXIMATE` | `GEOMETRIC_CENTER` |
| `MA_0135` | Centro, Rio de Janeiro - RJ, Brasil | R. Matagal, São Domingos do Azeitão - MA, 65888-000, Br | `APPROXIMATE` | `GEOMETRIC_CENTER` |
| `MT_0043` | Centro Norte, Várzea Grande - MT, Brasil | Av. Treze de Maio, 500 - CENTRO, Itiquira - MT, 78790-0 | `APPROXIMATE` | `ROOFTOP` |
| `MT_0048` | Centro Norte, Várzea Grande - MT, Brasil | Travessa Lucinda Kniess, 20 - Centro, Juruena - MT, 783 | `APPROXIMATE` | `ROOFTOP` |
| `MT_0053` | Centro Norte, Várzea Grande - MT, Brasil | Matupá - MT, Brasil | `APPROXIMATE` | `APPROXIMATE` |
| `MT_0091` | Centro, São José - SC, Brasil | R. Castelo Branco - São José do Povo, MT, 78773-000, Br | `APPROXIMATE` | `GEOMETRIC_CENTER` |
| `PA_0103` | Santa Maria - RS, Brasil | R. Honório Bastos, Oeiras do Pará - PA, 68470-000, Bras | `APPROXIMATE` | `GEOMETRIC_CENTER` |
| `PE_0009` | BR-101, KM 185 - Guaporanga, Biguaçu - SC, 88168-400, B | Tv. Agamenon Magalhães - Palmares, PE, 55540-000, Brasi | `ROOFTOP` | `GEOMETRIC_CENTER` |
| `PR_0139` | Centro Histórico, Porto Alegre - RS, Brasil | R. Joanino Miléo, 49 - CENTRO, Piraí do Sul - PR, 84240 | `APPROXIMATE` | `ROOFTOP` |
| `RR_0034` | 4°29'11.8"N 61°08'28.1"W - 1, 8, Piraí do Sul - PR, 842 | R. Caribe, Pacaraima - RR, 69345-000, Brasil | `ROOFTOP` | `GEOMETRIC_CENTER` |
