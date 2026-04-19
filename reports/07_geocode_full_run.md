# Geocode Full-Run Report

**Input:** `build/master_normalized.csv`
**Output:** `build/master_geocoded.csv`
**Raw log:** `build/geocode_raw_responses.jsonl`
**Provider:** `google_maps_geocoding_v1`

## Run counts

- **Total rows in dataset:** 2,271
- **Rows attempted (this run + prior resume):** 2,271
- **Successes (status OK):** 2,271
- **Failures (non-OK):** 0
- **Rows with `partial_match = true`:** 1,807

## Rows by `location_type`

| Location type | Count | Meaning |
|---------------|------:|---------|
| `ROOFTOP` | 1,492 | precise address-level match |
| `GEOMETRIC_CENTER` | 480 | centroid of street, neighborhood, or region |
| `APPROXIMATE` | 192 | imprecise — city-level or broader |
| `RANGE_INTERPOLATED` | 107 | interpolated between two address points |

## Quality flags across the OK set

These are stacked (a single row may be counted in several rows of this table).

| Flag | Rows |
|------|-----:|
| `partial_match = true` | 1,807 |
| `location_type = APPROXIMATE` | 192 |
| municipality missing from `formatted_address` | 140 |
| state code missing from `formatted_address` | 21 |
| coordinates outside Brazil bounding box (or missing) | 1 |

## 20 example suspicious rows for manual review

Ranked by a composite suspicion score. Out-of-bounds coordinates and municipality/state mismatches weight highest.

| row_id | Unit | Source muni, UF | formatted_address | lat,lng | location_type | partial | reasons |
|--------|------|-----------------|-------------------|---------|---------------|---------|---------|
| `BA_0139` | Hospital Municipal Paulo Souto | Jucuruçu, BA | Califórnia, EUA | 36.778261,-119.4179324 | `APPROXIMATE` | true | outside Brazil bounds; municipality not in formatted_address; state (BA) not in formatted_address; partial_match; APPROXIMATE |
| `AM_0053` | Polo Base Nova Esperança | Maués, AM | Nova Esperança, PR, 87600-000, Brasil | -23.1893414,-52.2003341 | `APPROXIMATE` | true | municipality not in formatted_address; state (AM) not in formatted_address; partial_match; APPROXIMATE |
| `AM_0056` | Polo Base Kwatá | Nova Olinda do Norte, AM | Rio Canumã, Amazonas, 69200-000, Brasil | -3.986118212068608,-59.10740553410074 | `APPROXIMATE` | true | municipality not in formatted_address; state (AM) not in formatted_address; partial_match; APPROXIMATE |
| `AM_0075` | 2º Pelotão Especial de Fronteira do Exército  | São Gabriel da Cachoeira, AM | Querari, Mitú, Vaupés, Colômbia | 1.04885,-69.85494 | `APPROXIMATE` | true | municipality not in formatted_address; state (AM) not in formatted_address; partial_match; APPROXIMATE |
| `AP_0024` | UBSI Bona Apalai | Óbidos/Pará, AP | Amapá, Brasil | 1.4441146,-52.0215415 | `APPROXIMATE` | true | municipality not in formatted_address; state (AP) not in formatted_address; partial_match; APPROXIMATE |
| `AP_0025` | UBSI Missão Tiriyó | Almerim/Pará, AP | Tiriós, Oriximiná - PA, 68270-000, Brasil | 2.2325789,-55.961233 | `APPROXIMATE` | true | municipality not in formatted_address; state (AP) not in formatted_address; partial_match; APPROXIMATE |
| `AP_0026` | UBSI Kuxaré | Almerim/Pará, AP | Tiriós, Oriximiná - PA, 68270-000, Brasil | 2.2325789,-55.961233 | `APPROXIMATE` | true | municipality not in formatted_address; state (AP) not in formatted_address; partial_match; APPROXIMATE |
| `BA_0015` | Hospital Municipal Santa Rita | Barra, BA | Bahia, Brasil | -11.4098737,-41.2808577 | `APPROXIMATE` | true | municipality not in formatted_address; state (BA) not in formatted_address; partial_match; APPROXIMATE |
| `BA_0199` | Hospital e Maternidade Maria Amelia Menezes S | Rio Real, BA | Centro, Rio de Janeiro - RJ, Brasil | -22.9012249,-43.1791747 | `APPROXIMATE` | true | municipality not in formatted_address; state (BA) not in formatted_address; partial_match; APPROXIMATE |
| `BA_0219` | Hospital Municipal de Sebastião Laranjeiras ( | Sebastião Laranjeiras, BA | Centro, Campinas - SP, Brasil | -22.9101744,-47.0593274 | `APPROXIMATE` | true | municipality not in formatted_address; state (BA) not in formatted_address; partial_match; APPROXIMATE |
| `MA_0053` | Hospital Regional de Grajau | GRAJAU, MA | São Roque, SP, Brasil | -23.5298156,-47.13740019999999 | `APPROXIMATE` | true | municipality not in formatted_address; state (MA) not in formatted_address; partial_match; APPROXIMATE |
| `MA_0135` | Hospital Municipal Rita Frca dos Santos Mãe R | SÃO DOMINGOS DO AZEITÃO, MA | Centro, Rio de Janeiro - RJ, Brasil | -22.9012249,-43.1791747 | `APPROXIMATE` | true | municipality not in formatted_address; state (MA) not in formatted_address; partial_match; APPROXIMATE |
| `MT_0091` | Centro de Saúde de São José | São José do Povo, MT | Centro, São José - SC, Brasil | -27.6129026,-48.6313699 | `APPROXIMATE` | true | municipality not in formatted_address; state (MT) not in formatted_address; partial_match; APPROXIMATE |
| `PA_0103` | Hospital de Pequeno Porte | Oeiras do Pará, PA | Santa Maria - RS, Brasil | -29.68949839999999,-53.7923441 | `APPROXIMATE` | true | municipality not in formatted_address; state (PA) not in formatted_address; partial_match; APPROXIMATE |
| `PR_0031` | Hospital Nossa Senhora da Aparecida - APMI | Capitão Leônidas Marques, PR | Cidade Baixa, Porto Alegre - RS, Brasil | -30.0401669,-51.2228614 | `APPROXIMATE` | true | municipality not in formatted_address; state (PR) not in formatted_address; partial_match; APPROXIMATE |
| `PR_0037` | Unidade de Pronto Atendimento Moacir Elias Fa | Castro, PR | Rio Branco, AC, Brasil | -9.9740249,-67.8098191 | `APPROXIMATE` | true | municipality not in formatted_address; state (PR) not in formatted_address; partial_match; APPROXIMATE |
| `PR_0139` | Hospital Municipal Santo Antonio | Piraí do Sul, PR | Centro Histórico, Porto Alegre - RS, Brasil | -30.0308043,-51.2278242 | `APPROXIMATE` | true | municipality not in formatted_address; state (PR) not in formatted_address; partial_match; APPROXIMATE |
| `AM_0023` | Hospital Deoclécio dos Santos | Careiro Castanho, AM | BR-319, Brasil | -5.7334519,-62.2751249 | `GEOMETRIC_CENTER` | true | municipality not in formatted_address; state (AM) not in formatted_address; partial_match |
| `PA_0055` | UPA porte III 24 HORAS Governador Almir Gabri | Castanhal, PA | BR-316, Brasil | -5.5553434,-42.6118734 | `GEOMETRIC_CENTER` | true | municipality not in formatted_address; state (PA) not in formatted_address; partial_match |
| `PE_0009` | Hospital Regional Sílvio Magalhães | Palmares, PE | BR-101, KM 185 - Guaporanga, Biguaçu - SC, 88168-400, Brasil | -27.4227872,-48.6243631 | `ROOFTOP` | true | municipality not in formatted_address; state (PE) not in formatted_address; partial_match |
