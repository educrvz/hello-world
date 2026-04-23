# SOS Antiveneno - Hospitais com Soro Antiveneno no Brasil

Aplicativo web mobile-first para encontrar o hospital mais próximo com soro antiveneno (PESA - Pontos Estratégicos de Soro Antiveneno).

## O que é?

No Brasil, nem todos os hospitais possuem soro antiveneno. O Ministério da Saúde mantém uma lista de hospitais de referência para acidentes com animais peçonhentos, mas essa informação está dispersa em PDFs separados por estado.

Este aplicativo reúne todos os dados em um só lugar e usa a localização do seu celular para mostrar os hospitais mais próximos com o soro que você precisa.

## Funcionalidades

- Localização automática via GPS
- Busca por tipo de acidente (escorpião, cobra, aranha)
- Filtro por tipo de antiveneno
- Números de telefone clicáveis para ligar direto
- Link para navegação (Google Maps)
- Compartilhamento via WhatsApp
- Funciona offline (PWA)
- Visualização em lista e mapa

## Dados

Os dados são extraídos dos PDFs oficiais do Ministério da Saúde (PESA) para
todos os 27 estados brasileiros, geocodificados via Google Maps, auditados
com um classificador de qualidade em várias camadas, e publicados como JSON
estático em `app/hospitals.json`.

O processo completo — extract → merge → normalize → QA → geocode → classify
v3 → repair → publish — é executado por:

```bash
./scripts/refresh_dataset.sh
```

Runbook completo: **[docs/PROCESS.md](docs/PROCESS.md)**.
Reports de cada etapa do último refresh: **[reports/](reports/)**.

## Feedback e correções de dados

Se você encontrou um pin errado, telefone desatualizado, hospital fechado ou
quer relatar um dado faltando, use o botão **"Reportar erro"** em cada cartão
do app — ele abre um formulário estruturado.

Contato do mantenedor: `contato.soroja@gmail.com`.

## Em caso de emergência

**Ligue 192 (SAMU)** — Serviço de Atendimento Móvel de Urgência

## Estrutura

```
scripts/        # Pipeline de dados (Python + shell orchestrator)
extracted/      # Um JSON por estado, extraído dos PDFs
Docs Estado/    # PDFs oficiais PESA, nomeados {UF}_{YYYYMMDD}.pdf
build/          # Artefatos intermediários + publish_ready_v1.csv (dataset final)
reports/        # Relatório por etapa do pipeline (01–10)
docs/           # PROCESS.md — runbook do refresh
app/            # Aplicativo web (HTML/CSS/JS estático) + hospitals.json
```

## Contribua

Este projeto é de código aberto. Correções de dados, sugestões e pull
requests são muito bem-vindos — abra uma issue ou PR no GitHub.
