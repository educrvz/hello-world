# Geocode Review Classification (v2)

**Input:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/master_geocoded.csv`
**Total rows classified:** 2,271

`partial_match` alone is **no longer** a trigger for manual review. Classification uses combined evidence from `location_type`, coordinate validity, state consistency, `formatted_address` structure, and place_id reuse.

## Bucket counts

| Bucket | Count | % | Output file |
|--------|------:|--:|-------------|
| `auto_accept` | 1,400 | 61.6% | `build/geocode_auto_accept.csv` |
| `watchlist` | 29 | 1.3% | `build/geocode_watchlist.csv` |
| `retry_queue` | 812 | 35.8% | `build/geocode_retry_queue.csv` |
| `manual_review_high_risk` | 30 | 1.3% | `build/geocode_manual_review_high_risk.csv` |
| **Total** | **2,271** | **100.0%** |  |

## Location type breakdown per bucket

| Bucket | `APPROXIMATE` | `GEOMETRIC_CENTER` | `RANGE_INTERPOLATED` | `ROOFTOP` |
|--------|-----:|-----:|-----:|-----:|
| `auto_accept` | 0 | 0 | 0 | 1400 |
| `watchlist` | 0 | 29 | 0 | 0 |
| `retry_queue` | 176 | 447 | 107 | 82 |
| `manual_review_high_risk` | 16 | 4 | 0 | 10 |

## High-risk rows for manual review (top 25)

| row_id | Source muni, UF | formatted_address | loc_type | reasons |
|--------|-----------------|-------------------|----------|---------|
| `AM_0075` | São Gabriel da Cachoeira, AM | Querari, Mitú, Vaupés, Colômbia | `APPROXIMATE` | formatted_address ends with non-Brazil country (Colômbia) |
| `AP_0025` | Almerim/Pará, AP | Tiriós, Oriximiná - PA, 68270-000, Brasil | `APPROXIMATE` | formatted_address state (PA) differs from source state (AP) |
| `AP_0026` | Almerim/Pará, AP | Tiriós, Oriximiná - PA, 68270-000, Brasil | `APPROXIMATE` | formatted_address state (PA) differs from source state (AP) |
| `BA_0139` | Jucuruçu, BA | Califórnia, EUA | `APPROXIMATE` | coordinates outside Brazil |
| `BA_0161` | Morpará, BA | R. Clemente Mariani, 82 - Morpará, BA, 47580-000, Brasil | `ROOFTOP` | formatted_address state (PA) differs from source state (BA) |
| `BA_0173` | Paramirim, BA | R. Herculano C. Martins, s/n - Paramirim, BA, 46190-000, Brasil | `ROOFTOP` | formatted_address state (PA) differs from source state (BA) |
| `BA_0174` | Paramirim, BA | Av. Centenário, 147 - Paramirim, BA, 46190-000, Brasil | `ROOFTOP` | formatted_address state (PA) differs from source state (BA) |
| `BA_0175` | Paratinga, BA | Av. Dr. Manoel Novaes - Paratinga, BA, 47500-000, Brasil | `GEOMETRIC_CENTER` | formatted_address state (PA) differs from source state (BA) |
| `BA_0199` | Rio Real, BA | Centro, Rio de Janeiro - RJ, Brasil | `APPROXIMATE` | formatted_address state (RJ) differs from source state (BA) |
| `BA_0219` | Sebastião Laranjeiras, BA | Centro, Campinas - SP, Brasil | `APPROXIMATE` | formatted_address state (SP) differs from source state (BA) |
| `GO_0045` | Itapaci, GO | Rua Tocantins, 7 - Itapaci, GO, 76360-000, Brasil | `ROOFTOP` | formatted_address state (TO) differs from source state (GO) |
| `MA_0135` | SÃO DOMINGOS DO AZEITÃO, MA | Centro, Rio de Janeiro - RJ, Brasil | `APPROXIMATE` | formatted_address state (RJ) differs from source state (MA) |
| `MG_0231` | Rio Paranaíba, MG | R. Ver. José Augusto da Silva, 98 - Rio Paranaíba, MG, 38810-000, Bras | `ROOFTOP` | formatted_address state (PA) differs from source state (MG) |
| `MG_0256` | São João do Paraíso, MG | R. Sebastião Costa Pereira - São João do Paraíso, MG, 39540-000, Brasi | `GEOMETRIC_CENTER` | formatted_address state (PA) differs from source state (MG) |
| `MT_0043` | Itiquira, MT | Centro Norte, Várzea Grande - MT, Brasil | `APPROXIMATE` | place_id reused across multiple unrelated municipalities |
| `MT_0048` | Juruena, MT | Centro Norte, Várzea Grande - MT, Brasil | `APPROXIMATE` | place_id reused across multiple unrelated municipalities |
| `MT_0053` | Matupá, MT | Centro Norte, Várzea Grande - MT, Brasil | `APPROXIMATE` | place_id reused across multiple unrelated municipalities |
| `MT_0087` | Salto do Céu, MT | R. Espírito Santo - Salto do Céu, MT, 78270-000, Brasil | `GEOMETRIC_CENTER` | formatted_address state (ES) differs from source state (MT) |
| `MT_0091` | São José do Povo, MT | Centro, São José - SC, Brasil | `APPROXIMATE` | formatted_address state (SC) differs from source state (MT) |
| `PA_0103` | Oeiras do Pará, PA | Santa Maria - RS, Brasil | `APPROXIMATE` | formatted_address state (RS) differs from source state (PA) |
| `PE_0009` | Palmares, PE | BR-101, KM 185 - Guaporanga, Biguaçu - SC, 88168-400, Brasil | `ROOFTOP` | formatted_address state (SC) differs from source state (PE) |
| `PR_0031` | Capitão Leônidas Marques, PR | Cidade Baixa, Porto Alegre - RS, Brasil | `APPROXIMATE` | formatted_address state (RS) differs from source state (PR) |
| `PR_0120` | Nova Aurora, PR | R. Alagoas, 305 - Nova Aurora, PR, 85410-000, Brasil | `ROOFTOP` | formatted_address state (AL) differs from source state (PR) |
| `PR_0139` | Piraí do Sul, PR | Centro Histórico, Porto Alegre - RS, Brasil | `APPROXIMATE` | formatted_address state (RS) differs from source state (PR) |
| `PR_0146` | Porto Amazonas, PR | R. Manoel Ribas, 85 - Porto Amazonas, PR, 84140-000, Brasil | `ROOFTOP` | formatted_address state (AM) differs from source state (PR) |

## Retry queue rows (top 25)

| row_id | Source muni, UF | formatted_address | loc_type | reasons |
|--------|-----------------|-------------------|----------|---------|
| `AC_0002` | Assis Brasil, AC | Seringal Paraguaçu, Assis Brasil - AC, 69935-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0003` | Brasiléia, AC | BR-317 & R. Raimundo Chaar, Assis Brasil - AC, 69935-000, Brasil | `GEOMETRIC_CENTER` | municipality not in formatted_address; partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0006` | Jordão, AC | Jordão - AC, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; formatted_address is generic (<4 segments or highway-only); partial_match with location_type=APPROXIMATE |
| `AC_0007` | Mâncio Lima, AC | Mancio Lima, Mâncio Lima - AC, 69990-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0008` | Manoel Urbano, AC | R. Francisco Freitas, Manoel Urbano - AC, 69950-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0009` | Marechal Thaumaturgo, AC | Mal. Thaumaturgo - AC, 69983-000, Brasil | `GEOMETRIC_CENTER` | municipality not in formatted_address; formatted_address is generic (<4 segments or highway-only); partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0011` | Porto Walter, AC | R. Mamede Cameli, Porto Walter - AC, 69982-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0013` | Santa Rosa do Purus, AC | R. 28 de - Rua do Marco, Santa Rosa do Purus - AC, 69955-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AC_0015` | Senador Guiomard, AC | R. Sen. Eduardo Asmar, 133 - Cohab, Sen. Guiomard - AC, 69925-000, Bra | `ROOFTOP` | municipality not in formatted_address |
| `AL_0001` | Arapiraca, AL | AL-220,Km 5 - Sen. Arnon de Melo, Arapiraca - AL, 57315-745, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0002` | Delmiro Gouveia, AL | R. Luiz Luna Torres, Delmiro Gouveia - AL, 57480-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0005` | Penedo, AL | R. Mateus R Ferreira - Santa Luzia, Penedo - AL, 57200-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0006` | Piranhas, AL | Av. Maceió - Piranhas, AL, 57460-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0007` | Santana do Ipanema, AL | Av. João Agostinho, Santana do Ipanema - AL, 57500-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AL_0014` | União dos Palmares, AL | AL-205 - União dos Palmares, AL, 57800-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AM_0001` | Alvarães, AM | Estr. Alvarães Nogueira, Alvarães - AM, 69475-000, Brasil | `GEOMETRIC_CENTER` | partial_match with location_type=GEOMETRIC_CENTER |
| `AM_0002` | Amaturá, AM | Centro, Amaturá - AM, 69620-000, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0003` | Anamã, AM | R. Álvaro Maia, 106, Anamã - AM, 69445-000, Brasil | `RANGE_INTERPOLATED` | partial_match with location_type=RANGE_INTERPOLATED |
| `AM_0004` | Anori, AM | Anori, AM, 69440-000, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0005` | Apuí, AM | Apuí, AM, 69265-000, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0006` | Atalaia do Norte, AM | Atalaia do Norte, AM, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; formatted_address is generic (<4 segments or highway-only); partial_match with location_type=APPROXIMATE |
| `AM_0007` | Atalaia do Norte, AM | Palmeiras do Javari, Atalaia do Norte - AM, 69650-000, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0008` | Atalaia do Norte, AM | Estirão do Equador, Atalaia do Norte - AM, 69650-000, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0009` | Atalaia do Norte, AM | Rio Ituí, Atalaia do Norte - AM, 69650-000, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |
| `AM_0010` | Atalaia do Norte, AM | Rio Curuçá, Atalaia do Norte - AM, 69650-000, Brasil | `APPROXIMATE` | location_type=APPROXIMATE; partial_match with location_type=APPROXIMATE |

## Watchlist samples (top 25)

| row_id | Source muni, UF | formatted_address | loc_type | reasons |
|--------|-----------------|-------------------|----------|---------|
| `BA_0020` | Belmonte, BA | R. Saldanha da Gama - Belmonte, BA, 45800-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `BA_0120` | Itarantim, BA | R. Maria Quitéria - Itarantim, BA, 45780-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `BA_0121` | Itarantim, BA | R. Maria Quitéria - Itarantim, BA, 45780-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `BA_0131` | Jaguaquara, BA | Av. Pio XII - Muritiba, Jaguaquara - BA, 45345-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `BA_0232` | Tapiramutá, BA | Av. Cafeeira - Tapiramutá, BA, 44840-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `CE_0031` | Pedra Branca, CE | R. Furtunato Silva - Bom Princípio, Pedra Branca - CE, 63630-000, Bras | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `GO_0007` | Aporé, GO | Av. João Nunes, Aporé - GO, 75825-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `GO_0057` | Mozarlândia, GO | R. São Paulo, Mozarlândia - GO, 76700-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `GO_0084` | Trindade, GO | Av. Tiradentes - St. Soares, Trindade - GO, 75380-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `MA_0036` | CANTANHEDE, MA | MA-332, Cantanhede - MA, 65465-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `MA_0049` | FEIRA NOVA DO MARANHÃO, MA | R. Tocantins - Centro, Feira Nova do Maranhão - MA, 65995-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `MA_0080` | MATINHA, MA | MA-014, Matinha - MA, 65218-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `MA_0092` | PAULINO NEVES, MA | MA-315, Paulino Neves - MA, 65585-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `MA_0152` | VILA NOVA DOS MARTIRIOS, MA | R. Pres. Mendes - Vila João Pinto, Vila Nova dos Martírios - MA, 65924 | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `MA_0154` | VITORINO FREIRE, MA | R. Eugênio Barros - Centro, Vitorino Freire - MA, 65320-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `MT_0020` | Campinápolis, MT | Centro, Campinápolis - MT, 78630-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `PA_0010` | Altamira, PA | Tv. Campinas - Jardim Uirapuru, Altamira - PA, 68374-140, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `PA_0085` | Marituba, PA | BR-316 - Almir Gabriel, Marituba - PA, 67105-290, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `PA_0117` | Prainha, PA | Tv. Paes de Carvalho - Prainha, PA, 68130-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `PA_0159` | Tailândia, PA | Av. Florianópolis - Bairro Novo, Tailândia - PA, 68695-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `PR_0082` | Ipiranga, PR | Rua Tereza de Jesus, Ipiranga - PR, 84450-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `RJ_0017` | Nova Iguaçu, RJ | Av. Henrique Duque Estrada Meyer - Posse, Nova Iguaçu - RJ, 26030-380, | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `RO_0028` | Porto Velho, RO | 415 303 - Av. Guaporé - Lagoa, Porto Velho - RO, 76812-329, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `RR_0005` | Iracema, RR | R. Elói Pereira - Iracema, RR, 69348-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |
| `SC_0028` | Ipira, SC | R. do Hospital, Ipira - SC, 89669-000, Brasil | `GEOMETRIC_CENTER` | location_type=GEOMETRIC_CENTER |

## Rules applied

- **Manual-review-high-risk triggers:** status != OK, lat/lng missing, coords outside Brazil, non-Brazil country string, UF mismatch between source and formatted_address, or place_id reused across >= 3 distinct (municipality, state) pairs.
- **Retry-queue triggers:** location_type=APPROXIMATE, municipality not present in formatted_address, formatted_address with <4 comma segments or a highway-only first segment, or `partial_match=true` paired with non-ROOFTOP location_type.
- **Watchlist:** status OK, in Brazil, correct state, location_type=GEOMETRIC_CENTER or RANGE_INTERPOLATED, no other flag fired. `partial_match` is tolerated here.
- **Auto-accept:** location_type=ROOFTOP and every check above is clean. `partial_match` by itself does not disqualify the row.
