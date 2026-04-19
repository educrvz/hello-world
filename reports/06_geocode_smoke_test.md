# Geocode Smoke Test

**Input:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/master_normalized.csv`
**Output:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/master_geocoded.csv`
**Raw responses:** `/Users/educruz/Documents/Claude/Projects/Hospitais_de_referencia/build/geocode_raw_responses.jsonl`
**Provider:** `google_maps_geocoding_v1`
**Completed at:** 2026-04-19T14:44:56Z

**Total rows in input:** 2,271
**Row attempt limit:** 50
**Attempted in this run:** 50
**Skipped (prior terminal status, resume):** 0
**Succeeded (status OK):** 50
**Failed (non-OK):** 0

## Status breakdown

| Status | Count |
|--------|------:|
| `OK` | 50 |

## 10 sample attempted rows

| row_id | status | geocode_query | formatted_address |
|--------|--------|---------------|-------------------|
| `AC_0001` | `OK` | Unidade Mista de Saúde de Acrelândia, Avenida Paraná, 346 – Centro, Acrelândia, ACRE, Brasil | Av. Paraná, 346 - centro, Acrelândia - AC, 69945-000, Brasil |
| `AC_0002` | `OK` | Unidade Mista de Assis Brasil, Rua D. Giocondo Maria Grotti, s/n - Centro, Assis Brasil, ACRE, Brasil | Seringal Paraguaçu, Assis Brasil - AC, 69935-000, Brasil |
| `AC_0003` | `OK` | Hospital de Clínicas Raimundo Chaar, BR 317, km 01, Bairro ALberto Castro s/n, Brasiléia, ACRE, Brasil | BR-317 & R. Raimundo Chaar, Assis Brasil - AC, 69935-000, Brasil |
| `AC_0004` | `OK` | Hospital Regional do Juruá, Avenida 25 de Agosto, 5121 - Aeroporto Velho, Cruzeiro do Sul, ACRE, Brasil | Av. 25 de Agosto, 5121 - Aeroporto Velho, Cruzeiro do Sul - AC, 69895-000, Brasil |
| `AC_0005` | `OK` | Hospital Geral de Feijó, Avenida Mal. Deodoro, s/n - Centro, Feijó, ACRE, Brasil | Av. Mal. Deodoro, s/n - centro, Feijó - AC, 69960-000, Brasil |
| `AC_0006` | `OK` | Hospital da Família de Jordão, Rua Romildo Magalhães, s/n – Centro, Jordão, ACRE, Brasil | Jordão - AC, Brasil |
| `AC_0007` | `OK` | Hospital Dr. Abel Pinheiro Maciel Filho, Avenida Japiim, s/n - Centro, Mâncio Lima, ACRE, Brasil | Mancio Lima, Mâncio Lima - AC, 69990-000, Brasil |
| `AC_0008` | `OK` | Unidade Mista de Manuel Urbano, Rua Francisco Freitas, s/n - São José, Manoel Urbano, ACRE, Brasil | R. Francisco Freitas, Manoel Urbano - AC, 69950-000, Brasil |
| `AC_0009` | `OK` | Unidade Mista de Marechal Thaumaturgo, Rua 5 de novembro, s/n - Centro, Marechal Thaumaturgo, ACRE, Brasil | Mal. Thaumaturgo - AC, 69983-000, Brasil |
| `AC_0010` | `OK` | Hospital Dr. Manoel Marinho Monte, Rua Epitácio Pessoa, 550 - Centro, Plácido de Castro, ACRE, Brasil | 69928-000 - R. José Ferreira Lima, 278-454 - Centro, Plácido de Castro - AC, 69928-000, Brasil |
