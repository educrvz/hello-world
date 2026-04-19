# Geocode Review Classification (v3)

**Input:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/master_geocoded.csv`
**Total rows classified:** 2,271

### Changes from v2

- `geocoded_state_abbr` is now parsed **only** from the strict `- UF` end-pattern in `formatted_address`. Substring matching against full state names (which false-matched street names, municipality names, and unit names in v2) has been **removed**.
- `source_state_abbr` from the extracted JSON filename (e.g. `BA.json` → `BA`) is treated as the expected state context.
- UF mismatch is **no longer automatically catastrophic**. For special remote / indigenous / military / support units (Polo Base, UBSI, Pelotão, Missão, Fronteira, Base Indígena, DSEI, PEF, CASAI, Aldeia, Yanomami), a mismatch is downgraded to `retry_queue` unless combined with another severe signal.

## Bucket counts

| Bucket | Count | % | Output file |
|--------|------:|--:|-------------|
| `auto_accept` | 1,441 | 63.5% | `build/geocode_auto_accept_v3.csv` |
| `watchlist` | 29 | 1.3% | `build/geocode_watchlist_v3.csv` |
| `retry_queue` | 787 | 34.7% | `build/geocode_retry_queue_v3.csv` |
| `manual_review_high_risk` | 14 | 0.6% | `build/geocode_manual_review_high_risk_v3.csv` |
| **Total** | **2,271** | **100.0%** |  |

## Location type breakdown per bucket

| Bucket | `APPROXIMATE` | `GEOMETRIC_CENTER` | `RANGE_INTERPOLATED` | `ROOFTOP` |
|--------|-----:|-----:|-----:|-----:|
| `auto_accept` | 0 | 0 | 0 | 1441 |
| `watchlist` | 0 | 29 | 0 | 0 |
| `retry_queue` | 167 | 453 | 107 | 60 |
| `manual_review_high_risk` | 12 | 0 | 0 | 2 |

## High-risk rows (top 25)

| row_id | Source muni, UF | FA | geocoded_uf | special | reasons |
|--------|-----------------|----|-------------|---------|---------|
| `AM_0075` | São Gabriel da Cachoeira, AM | Querari, Mitú, Vaupés, Colômbia | `—` | yes | formatted_address ends with non-Brazil country (Colômbia) |
| `BA_0139` | Jucuruçu, BA | Califórnia, EUA | `—` |  | coordinates outside Brazil |
| `BA_0199` | Rio Real, BA | Centro, Rio de Janeiro - RJ, Brasil | `RJ` |  | geocoded_state_abbr=RJ differs from source_state_abbr=BA (standard hospital-type unit) |
| `BA_0219` | Sebastião Laranjeiras, BA | Centro, Campinas - SP, Brasil | `SP` |  | geocoded_state_abbr=SP differs from source_state_abbr=BA (standard hospital-type unit) |
| `MA_0135` | SÃO DOMINGOS DO AZEITÃO, MA | Centro, Rio de Janeiro - RJ, Brasil | `RJ` |  | geocoded_state_abbr=RJ differs from source_state_abbr=MA (standard hospital-type unit) |
| `MT_0043` | Itiquira, MT | Centro Norte, Várzea Grande - MT, Brasil | `MT` |  | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0048` | Juruena, MT | Centro Norte, Várzea Grande - MT, Brasil | `MT` |  | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0053` | Matupá, MT | Centro Norte, Várzea Grande - MT, Brasil | `MT` |  | place_id reused across multiple unrelated (municipality, state) pairs |
| `MT_0091` | São José do Povo, MT | Centro, São José - SC, Brasil | `SC` |  | geocoded_state_abbr=SC differs from source_state_abbr=MT (standard hospital-type unit) |
| `PA_0103` | Oeiras do Pará, PA | Santa Maria - RS, Brasil | `RS` |  | geocoded_state_abbr=RS differs from source_state_abbr=PA (standard hospital-type unit) |
| `PE_0009` | Palmares, PE | BR-101, KM 185 - Guaporanga, Biguaçu - SC, 88168-400, B | `SC` |  | geocoded_state_abbr=SC differs from source_state_abbr=PE (standard hospital-type unit) |
| `PR_0031` | Capitão Leônidas Marques, PR | Cidade Baixa, Porto Alegre - RS, Brasil | `RS` |  | geocoded_state_abbr=RS differs from source_state_abbr=PR (standard hospital-type unit) |
| `PR_0139` | Piraí do Sul, PR | Centro Histórico, Porto Alegre - RS, Brasil | `RS` |  | geocoded_state_abbr=RS differs from source_state_abbr=PR (standard hospital-type unit) |
| `RR_0034` | Pacaraima, RR | 4°29'11.8"N 61°08'28.1"W - 1, 8, Piraí do Sul - PR, 842 | `PR` |  | geocoded_state_abbr=PR differs from source_state_abbr=RR (standard hospital-type unit) |

## Retry queue rows (top 25)

| row_id | Source muni, UF | FA | geocoded_uf | special | reasons |
|--------|-----------------|----|-------------|---------|---------|
| `AC_0002` | Assis Brasil, AC | Seringal Paraguaçu, Assis Brasil - AC, 69935-000, Brasi | `AC` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0003` | Brasiléia, AC | BR-317 & R. Raimundo Chaar, Assis Brasil - AC, 69935-00 | `AC` |  | municipality not in formatted_address; partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0006` | Jordão, AC | Jordão - AC, Brasil | `AC` |  | location_type=APPROXIMATE; formatted_address is generic (<4 segments or highway-only); partial_match with location_type=APPROXIMATE |
| `AC_0007` | Mâncio Lima, AC | Mancio Lima, Mâncio Lima - AC, 69990-000, Brasil | `AC` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0008` | Manoel Urbano, AC | R. Francisco Freitas, Manoel Urbano - AC, 69950-000, Br | `AC` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0009` | Marechal Thaumaturgo, AC | Mal. Thaumaturgo - AC, 69983-000, Brasil | `AC` |  | municipality not in formatted_address; formatted_address is generic (<4 segments or highway-only); partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0011` | Porto Walter, AC | R. Mamede Cameli, Porto Walter - AC, 69982-000, Brasil | `AC` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0013` | Santa Rosa do Purus, AC | R. 28 de - Rua do Marco, Santa Rosa do Purus - AC, 6995 | `AC` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0015` | Senador Guiomard, AC | R. Sen. Eduardo Asmar, 133 - Cohab, Sen. Guiomard - AC, | `AC` |  | municipality not in formatted_address |
| `AL_0001` | Arapiraca, AL | AL-220,Km 5 - Sen. Arnon de Melo, Arapiraca - AL, 57315 | `AL` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0002` | Delmiro Gouveia, AL | R. Luiz Luna Torres, Delmiro Gouveia - AL, 57480-000, B | `AL` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0005` | Penedo, AL | R. Mateus R Ferreira - Santa Luzia, Penedo - AL, 57200- | `AL` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0006` | Piranhas, AL | Av. Maceió - Piranhas, AL, 57460-000, Brasil | `—` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0007` | Santana do Ipanema, AL | Av. João Agostinho, Santana do Ipanema - AL, 57500-000, | `AL` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0014` | União dos Palmares, AL | AL-205 - União dos Palmares, AL, 57800-000, Brasil | `—` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AM_0001` | Alvarães, AM | Estr. Alvarães Nogueira, Alvarães - AM, 69475-000, Bras | `AM` |  | partial_match with location_type=GEOMETRIC_CENTER |
| `AM_0002` | Amaturá, AM | Centro, Amaturá - AM, 69620-000, Brasil | `AM` |  | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0003` | Anamã, AM | R. Álvaro Maia, 106, Anamã - AM, 69445-000, Brasil | `AM` |  | partial_match with location_type=RANGE_INTERPOLATED |
| `AM_0004` | Anori, AM | Anori, AM, 69440-000, Brasil | `—` |  | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0005` | Apuí, AM | Apuí, AM, 69265-000, Brasil | `—` |  | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0006` | Atalaia do Norte, AM | Atalaia do Norte, AM, Brasil | `—` |  | location_type=APPROXIMATE; formatted_address is generic (<4 segments or highway-only); partial_match with location_type=APPROXIMATE |
| `AM_0007` | Atalaia do Norte, AM | Palmeiras do Javari, Atalaia do Norte - AM, 69650-000,  | `AM` | yes | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0008` | Atalaia do Norte, AM | Estirão do Equador, Atalaia do Norte - AM, 69650-000, B | `AM` | yes | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0009` | Atalaia do Norte, AM | Rio Ituí, Atalaia do Norte - AM, 69650-000, Brasil | `AM` | yes | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0010` | Atalaia do Norte, AM | Rio Curuçá, Atalaia do Norte - AM, 69650-000, Brasil | `AM` | yes | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |

## Watchlist samples (top 25)

| row_id | Source muni, UF | FA | geocoded_uf | special | reasons |
|--------|-----------------|----|-------------|---------|---------|
| `BA_0020` | Belmonte, BA | R. Saldanha da Gama - Belmonte, BA, 45800-000, Brasil | `—` |  | location_type=GEOMETRIC_CENTER |
| `BA_0120` | Itarantim, BA | R. Maria Quitéria - Itarantim, BA, 45780-000, Brasil | `—` |  | location_type=GEOMETRIC_CENTER |
| `BA_0121` | Itarantim, BA | R. Maria Quitéria - Itarantim, BA, 45780-000, Brasil | `—` |  | location_type=GEOMETRIC_CENTER |
| `BA_0131` | Jaguaquara, BA | Av. Pio XII - Muritiba, Jaguaquara - BA, 45345-000, Bra | `BA` |  | location_type=GEOMETRIC_CENTER |
| `BA_0232` | Tapiramutá, BA | Av. Cafeeira - Tapiramutá, BA, 44840-000, Brasil | `—` |  | location_type=GEOMETRIC_CENTER |
| `CE_0031` | Pedra Branca, CE | R. Furtunato Silva - Bom Princípio, Pedra Branca - CE,  | `CE` |  | location_type=GEOMETRIC_CENTER |
| `GO_0007` | Aporé, GO | Av. João Nunes, Aporé - GO, 75825-000, Brasil | `GO` |  | location_type=GEOMETRIC_CENTER |
| `GO_0057` | Mozarlândia, GO | R. São Paulo, Mozarlândia - GO, 76700-000, Brasil | `GO` |  | location_type=GEOMETRIC_CENTER |
| `GO_0084` | Trindade, GO | Av. Tiradentes - St. Soares, Trindade - GO, 75380-000,  | `GO` |  | location_type=GEOMETRIC_CENTER |
| `MA_0036` | CANTANHEDE, MA | MA-332, Cantanhede - MA, 65465-000, Brasil | `MA` |  | location_type=GEOMETRIC_CENTER |
| `MA_0049` | FEIRA NOVA DO MARANHÃO, MA | R. Tocantins - Centro, Feira Nova do Maranhão - MA, 659 | `MA` |  | location_type=GEOMETRIC_CENTER |
| `MA_0080` | MATINHA, MA | MA-014, Matinha - MA, 65218-000, Brasil | `MA` |  | location_type=GEOMETRIC_CENTER |
| `MA_0092` | PAULINO NEVES, MA | MA-315, Paulino Neves - MA, 65585-000, Brasil | `MA` |  | location_type=GEOMETRIC_CENTER |
| `MA_0152` | VILA NOVA DOS MARTIRIOS, MA | R. Pres. Mendes - Vila João Pinto, Vila Nova dos Martír | `MA` |  | location_type=GEOMETRIC_CENTER |
| `MA_0154` | VITORINO FREIRE, MA | R. Eugênio Barros - Centro, Vitorino Freire - MA, 65320 | `MA` |  | location_type=GEOMETRIC_CENTER |
| `MT_0020` | Campinápolis, MT | Centro, Campinápolis - MT, 78630-000, Brasil | `MT` |  | location_type=GEOMETRIC_CENTER |
| `PA_0010` | Altamira, PA | Tv. Campinas - Jardim Uirapuru, Altamira - PA, 68374-14 | `PA` |  | location_type=GEOMETRIC_CENTER |
| `PA_0085` | Marituba, PA | BR-316 - Almir Gabriel, Marituba - PA, 67105-290, Brasi | `PA` |  | location_type=GEOMETRIC_CENTER |
| `PA_0117` | Prainha, PA | Tv. Paes de Carvalho - Prainha, PA, 68130-000, Brasil | `—` |  | location_type=GEOMETRIC_CENTER |
| `PA_0159` | Tailândia, PA | Av. Florianópolis - Bairro Novo, Tailândia - PA, 68695- | `PA` |  | location_type=GEOMETRIC_CENTER |
| `PR_0082` | Ipiranga, PR | Rua Tereza de Jesus, Ipiranga - PR, 84450-000, Brasil | `PR` |  | location_type=GEOMETRIC_CENTER |
| `RJ_0017` | Nova Iguaçu, RJ | Av. Henrique Duque Estrada Meyer - Posse, Nova Iguaçu - | `RJ` |  | location_type=GEOMETRIC_CENTER |
| `RO_0028` | Porto Velho, RO | 415 303 - Av. Guaporé - Lagoa, Porto Velho - RO, 76812- | `RO` |  | location_type=GEOMETRIC_CENTER |
| `RR_0005` | Iracema, RR | R. Elói Pereira - Iracema, RR, 69348-000, Brasil | `—` |  | location_type=GEOMETRIC_CENTER |
| `SC_0028` | Ipira, SC | R. do Hospital, Ipira - SC, 89669-000, Brasil | `SC` |  | location_type=GEOMETRIC_CENTER |

## Parser confirmation

- UF-from-FA regex: ``-\s*([A-Z]{2})(?=\s*(?:,|$))`` (rightmost match only).
- **No substring matching against full state names** anywhere inside `formatted_address`.
- Special-unit regex: `(?:\bpolo\s*base\b|\bubsi\b|\bmiss[ãa]o\b|\bpelot[ãa]o\b|\bfronteira\b|\bbase\s*ind[ií]gena\b|\bind[ií]gena\b|\byanomami\b|\bianomami\b|\bdsei\b|\bpef\b|\bcasai\b|\bcasa\s*de\s*sa[uú]de\s*ind[ií]gena\b|\bpost[oa]\s*ind[ií]gena\b|\baldeia\b)`
- Place-id reuse threshold: >= 3 distinct (municipality, state) origins.
