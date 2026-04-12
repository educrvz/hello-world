# Download PESA Hospital PDFs — Instructions for Claude Computer

## Objective

Download all 27 Brazilian state PDF files containing anti-venom hospital (PESA) data from the Ministry of Health website. Save each PDF to the `data/pdfs/` folder in this project.

---

## Step 1: Create the output directory

Create the folder `data/pdfs/` in this project if it doesn't already exist.

---

## Step 2: Navigate to the index page

Go to:
```
https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia
```

This page lists all Brazilian states with links to their PESA hospital PDFs. The page is **paginated** — there are 2 pages:
- Page 1: `?b_start:int=0` (default)
- Page 2: `?b_start:int=15`

---

## Step 3: Download all 27 state PDFs

Each state has a PDF download link. The download URL pattern is:
```
https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/{state-slug}/@@download/file
```

Download each PDF and save it with the filename `{state-slug}.pdf`.

Here are all 27 states with their slugs and direct download URLs:

| # | State | Slug | Download URL |
|---|-------|------|-------------|
| 1 | Acre | `acre` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/acre/@@download/file` |
| 2 | Alagoas | `alagoas` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/alagoas/@@download/file` |
| 3 | Amapa | `amapa` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/amapa/@@download/file` |
| 4 | Amazonas | `amazonas` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/amazonas/@@download/file` |
| 5 | Bahia | `bahia` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/bahia/@@download/file` |
| 6 | Ceara | `ceara` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/ceara/@@download/file` |
| 7 | Distrito Federal | `distrito-federal` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/distrito-federal/@@download/file` |
| 8 | Espirito Santo | `espirito-santo` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/espirito-santo/@@download/file` |
| 9 | Goias | `goias` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/goias/@@download/file` |
| 10 | Maranhao | `maranhao` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/maranhao/@@download/file` |
| 11 | Mato Grosso | `mato-grosso` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/mato-grosso/@@download/file` |
| 12 | Mato Grosso do Sul | `mato-grosso-do-sul` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/mato-grosso-do-sul/@@download/file` |
| 13 | Minas Gerais | `minas-gerais` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/minas-gerais/@@download/file` |
| 14 | Para | `para` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/para/@@download/file` |
| 15 | Paraiba | `paraiba` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/paraiba/@@download/file` |
| 16 | Parana | `parana` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/parana/@@download/file` |
| 17 | Pernambuco | `pernambuco` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/pernambuco/@@download/file` |
| 18 | Piaui | `piaui` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/piaui/@@download/file` |
| 19 | Rio de Janeiro | `rio-de-janeiro` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/rio-de-janeiro/@@download/file` |
| 20 | Rio Grande do Norte | `rio-grande-do-norte` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/rio-grande-do-norte/@@download/file` |
| 21 | Rio Grande do Sul | `rio-grande-do-sul` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/rio-grande-do-sul/@@download/file` |
| 22 | Rondonia | `rondonia` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/rondonia/@@download/file` |
| 23 | Roraima | `roraima` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/roraima/@@download/file` |
| 24 | Santa Catarina | `santa-catarina` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/santa-catarina/@@download/file` |
| 25 | Sao Paulo | `sao-paulo` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/sao-paulo/@@download/file` |
| 26 | Sergipe | `sergipe` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/sergipe/@@download/file` |
| 27 | Tocantins | `tocantins` | `https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/a/animais-peconhentos/hospitais-de-referencia/tocantins/@@download/file` |

---

## Step 4: Verify downloads

After downloading, confirm that the `data/pdfs/` folder contains exactly 27 PDF files:

```
data/pdfs/
├── acre.pdf
├── alagoas.pdf
├── amapa.pdf
├── amazonas.pdf
├── bahia.pdf
├── ceara.pdf
├── distrito-federal.pdf
├── espirito-santo.pdf
├── goias.pdf
├── maranhao.pdf
├── mato-grosso.pdf
├── mato-grosso-do-sul.pdf
├── minas-gerais.pdf
├── para.pdf
├── paraiba.pdf
├── parana.pdf
├── pernambuco.pdf
├── piaui.pdf
├── rio-de-janeiro.pdf
├── rio-grande-do-norte.pdf
├── rio-grande-do-sul.pdf
├── rondonia.pdf
├── roraima.pdf
├── santa-catarina.pdf
├── sao-paulo.pdf
├── sergipe.pdf
└── tocantins.pdf
```

Each file should be a valid PDF (not an HTML error page). You can verify by checking that each file starts with `%PDF` or by attempting to open one.

---

## Important Notes

- If any download URL returns a 404 or redirects to an HTML page, navigate to the index page manually and find the correct link for that state.
- Some states may have updated their PDF links. If the direct URL doesn't work, click through from the index page: find the state name, click it, then download the file.
- The gov.br website may be slow. Be patient with downloads.
- If the page layout has changed, look for links containing the state name that lead to downloadable files (PDF or similar).

---

## After Downloading

Once all 27 PDFs are saved to `data/pdfs/`, return to the Claude Code session. The scraper (`data/scraper.py`) will parse these local PDF files to extract hospital data.
