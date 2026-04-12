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

Os dados são extraídos dos PDFs oficiais do Ministério da Saúde (PESA) para todos os 27 estados brasileiros, geocodificados e disponibilizados como JSON estático.

## Em caso de emergência

**Ligue 192 (SAMU)** — Serviço de Atendimento Móvel de Urgência

## Estrutura

```
data/           # Scripts de extração de dados (Python)
app/            # Aplicativo web (HTML/CSS/JS estático)
```

## Licença

MIT
