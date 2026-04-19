# Pre-Geocode QA/QC Report

**Input:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/master_normalized.csv`
**Total rows inspected:** 2,271

**Review files written (no rows deleted or modified):**
- `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/review_missing_fields.csv`
- `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/review_possible_duplicates.csv`

## 1. Missing critical fields

**Rows flagged:** 4

A row can match more than one condition below.

| Missing condition | Rows |
|-------------------|-----:|
| `health_unit_name_clean` empty | 0 |
| `municipality_clean` empty | 0 |
| `state_clean` empty | 0 |
| `address_clean` AND `cnes` both empty | 4 |

## 2. Possible duplicates

Each key below is checked independently; a single row can appear in multiple groups.

| Key | Duplicate groups | Rows involved |
|-----|----------------:|--------------:|
| `cnes` (non-empty) | 14 | 29 |
| `health_unit_name_clean + municipality_clean + state_clean` | 3 | 6 |
| `geocode_query` (non-empty) | 2 | 4 |

### Top `cnes` duplicate groups

| cnes | Rows | States involved | Sample unit name |
|------|-----:|-----------------|------------------|
| `2115786` | 3 | MG | Hospital de Pronto Socorro |
| `2417456` | 2 | BA | Hospital Regional de Itarantim |
| `2451573` | 2 | MA | Hospital Jorge Oliveira |
| `2462095` | 2 | MA | Hospital e Maternidade Nayla Gonçalo |
| `2419653` | 2 | MG, SC | Hospital Nossa Senhora da Conceição |
| `6875343` | 2 | MG | Central de Rede de Frio |
| `9204970` | 2 | MT | Unidade de Pronto Atendimento |
| `3028925` | 2 | MT | Hospital da Criança Wilma Bohac Francisco |
| `2314819` | 2 | PA | Hospital Municipal Luis Carlos de Souza |
| `2677024` | 2 | PA | Unidade Mista/Ubs |
| `2798484` | 2 | RO | Hospital de Pequeno Porte Osvaldo Cruz |
| `2319705` | 2 | RR | Unidade Básica Jacir Vicente IOP |
| `2665883` | 2 | SC, SP | Hospital Santa Terezinha |
| `2078139` | 2 | SP | HOSPITAL Santa Casa - Piedade |

### Top `name + municipality + state` duplicate groups

| Key | Rows |
|-----|-----:|
| `Hospital Regional de Itarantim | Itarantim | BAHIA` | 2 |
| `Hospital Jorge Oliveira | ARARI | MARANHÃO` | 2 |
| `Unidade Básica Jacir Vicente IOP | Amajari | RORAIMA` | 2 |

### Top `geocode_query` duplicate groups

| Query | Rows |
|-------|-----:|
| `Hospital Regional de Itarantim, Rua Maria Quitéria, s/n – Centro, Itarantim, BAHIA, Brasil` | 2 |
| `Unidade Básica Jacir Vicente IOP, Avenida Antonio José Altino, s/n - Tepequem, Amajari, RORAIMA, Brasil` | 2 |
