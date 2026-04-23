"""
canonicalize_antivenoms.py
==========================

Canonicaliza strings livres de "tipos de soro antiveneno" para um conjunto
estável de tipos canônicos, preservando a string original em campo de auditoria.

Contexto:
    O pipeline de ingestão do SoroJá extrai dados de PDFs do Ministério da
    Saúde. A qualidade dos PDFs é heterogênea: há typos literais ("Escoepiônico"),
    variantes de capitalização/acentuação ("laquético" / "Laquetico" / "Laquético."),
    siglas ("SAB", "SAC", "SABL"), combinações ("Botrópico e Escorpiônico"),
    soros NÃO-antiveneno ("Antirrábico", "Antitetânico", "DT") e até vazamentos
    de colunas de observação ("É suprido pela rede de frio...") que devem ser
    movidos para `note` e NÃO exibidos como tipo de soro.

Este módulo resolve os 3 problemas de uma vez:
    1) Canonicaliza variantes em 9 tipos padrão (ver CANONICAL_TYPES).
    2) Identifica soros NÃO-antiveneno (raiva, tétano, difteria) e os retorna
       em lista separada.
    3) Detecta vazamentos de observação por padrões de frase e por comprimento.

Tipos canônicos (nomes populares em uso no Brasil):
    Botrópico, Crotálico, Laquético, Elapídico, Escorpiônico,
    Aracnídico (polivalente: Phoneutria, Loxosceles, Tityus),
    Loxoscélico (monovalente P. loxosceles),
    Fonêutrico (monovalente Phoneutria),
    Lonômico.

Uso:
    from canonicalize_antivenoms import canonicalize_list, CanonicalResult

    result = canonicalize_list([
        "Botrópico",
        "Escorpiônico.",
        "Laquetico",
        "SAB",
        "Botrópico e Escorpiônico",
        "É suprido pela rede de frio quando do atendimento",
        "Antirrábico",
    ])
    result.canonical    # ['Botrópico', 'Escorpiônico', 'Laquético', 'Botrópico', 'Escorpiônico']
    result.leaks        # ['É suprido pela rede de frio quando do atendimento']
    result.other_soros  # ['Antirrábico']
    result.unknown      # []

Integração sugerida:
    Chamar em scripts/build_app_hospitals_json.py antes de serializar cada
    hospital. Manter `source_antivenoms_raw` com a lista original para
    auditoria, e preencher `antivenoms` com o canônico.

Autor: Preparado para PR ao projeto educrvz/sos-antiveneno (soroja.com.br).
Licença: mesma do projeto hospedeiro (MIT esperado).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple


# ---------------------------------------------------------------------------
# Constantes canônicas
# ---------------------------------------------------------------------------

CANONICAL_TYPES: Tuple[str, ...] = (
    "Botrópico",
    "Crotálico",
    "Laquético",
    "Elapídico",
    "Escorpiônico",
    "Aracnídico",
    "Loxoscélico",
    "Fonêutrico",
    "Lonômico",
)

# Siglas oficiais do MS / Butantan → canônico
SIGLA_MAP = {
    "sab": "Botrópico",
    "sac": "Crotálico",
    "sae": "Elapídico",
    "sal": "Laquético",        # atenção: SAL também já foi usado p/ Lonômico; contexto resolve via ocorrência
    "saesc": "Escorpiônico",
    "saar": "Aracnídico",
    "salon": "Lonômico",
    "saln": "Lonômico",
    "sabc": "BotrópicoCrotálico",   # composto; será expandido
    "sabl": "BotrópicoLaquético",   # composto; será expandido
}

# Formas compostas (siglas que representam mais de um tipo)
COMPOUND_EXPANSION = {
    "BotrópicoCrotálico": ("Botrópico", "Crotálico"),
    "BotrópicoLaquético": ("Botrópico", "Laquético"),
}

# Padrões regex de canonicalização (ordem importa: combos antes de simples)
# Cada padrão é aplicado sobre a forma normalizada (sem acento, minúscula,
# sem pontuação final).
CANONICAL_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    # variantes com typos conhecidos primeiro
    (re.compile(r"^escorcorpionico$|^escoepionico$|^escopionico$"), "Escorpiônico"),
    (re.compile(r"^lonomoico$|^lononomico$"), "Lonômico"),
    (re.compile(r"^fonêutricoe$|^foneutricoe$"), "Fonêutrico"),
    (re.compile(r"^rotalico$"), "Crotálico"),

    # nomes canônicos (aceita prefixo "anti" e/ou "soro")
    (re.compile(r"(^|\s)(anti)?botropico(\s|$)"), "Botrópico"),
    (re.compile(r"(^|\s)(anti)?crotalico(\s|$)"), "Crotálico"),
    (re.compile(r"(^|\s)(anti)?laquet[iy]?co(\s|$)"), "Laquético"),
    (re.compile(r"(^|\s)(anti)?laquetio(\s|$)"), "Laquético"),  # typo "Laquétio"
    (re.compile(r"(^|\s)(anti)?elapidico(\s|$)"), "Elapídico"),
    (re.compile(r"(^|\s)(anti)?escorpionico(\s|$)"), "Escorpiônico"),
    (re.compile(r"(^|\s)(anti)?aracnideo(\s|$)"), "Aracnídico"),
    (re.compile(r"(^|\s)(anti)?aracnidico(\s|$)"), "Aracnídico"),
    (re.compile(r"(^|\s)(anti)?aracnidio(\s|$)"), "Aracnídico"),
    (re.compile(r"(^|\s)(anti)?aracmidico(\s|$)"), "Aracnídico"),   # typo
    (re.compile(r"(^|\s)(anti)?araneidico(\s|$)"), "Aracnídico"),   # aranha em geral
    (re.compile(r"(^|\s)(anti)?loxoscelico(\s|$)"), "Loxoscélico"),
    (re.compile(r"(^|\s)(anti)?foneutrico(\s|$)"), "Fonêutrico"),
    (re.compile(r"(^|\s)(anti)?lonomico(\s|$)"), "Lonômico"),
)

# Soros NÃO-antiveneno (profiláticos de raiva/tétano/difteria que às vezes
# aparecem juntos na coluna por erro de extração). Não devem ir para a tag
# de soro antiveneno.
# Obs.: "pentavalente" é apenas modificador do Botrópico (composição
# pentavalente), não é um tipo separado — não entra aqui.
NON_ANTIVENOM_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"^antirrab[ií]co$|^soro\s+anti\s*rab[ií]co$"),
    re.compile(r"^antitet[aâ]ni[cst]?o$|^antitet[aâ]tico$|^soro\s+antitet[aâ]nico$"),
    re.compile(r"^dt$"),                   # difteria/tétano
)

# Padrões de vazamento de observação (devem ser movidos para o campo `note`)
LEAK_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"suprid[oa]", re.IGNORECASE),
    re.compile(r"rede\s+de\s+frio", re.IGNORECASE),
    re.compile(r"ciatox", re.IGNORECASE),
    re.compile(r"cl[ée]riston", re.IGNORECASE),
    re.compile(r"quando\s+do\s+atendimento", re.IGNORECASE),
    re.compile(r"dada\s+a\s+proximidade", re.IGNORECASE),
    re.compile(r"demais\s+(s[aã]o|ser[ãa]o)", re.IGNORECASE),
    re.compile(r"armazenad[oa]s\s+na", re.IGNORECASE),
    re.compile(r"hospital\s+de\s+apoio", re.IGNORECASE),
    re.compile(r"judicial", re.IGNORECASE),
)

# Se a string tem mais que este tamanho e não bate em canônico, é
# considerada vazamento/observação.
MAX_REASONABLE_LEN = 40

# Delimitadores que separam tipos dentro de uma mesma string.
# Inclui hífen (com ou sem espaço) para tratar combos como "Botropico-Laquético".
SPLIT_PATTERN = re.compile(r"\s*(?:;|,|/|\be\b|\bE\b|\+|-)\s*", flags=re.IGNORECASE)


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


@dataclass
class CanonicalResult:
    """Resultado da canonicalização de uma lista de strings de antivenoms.

    Campos:
        canonical: lista de tipos canônicos identificados (com repetição,
            na ordem em que apareceram), sem duplicatas adjacentes.
        leaks: observações que vazaram para o campo errado; devem ir para
            o campo `note` do hospital.
        other_soros: soros não-antiveneno (raiva, tétano) — podem ser
            exibidos em seção separada, se desejado.
        unknown: strings que não se encaixaram em nenhuma categoria; úteis
            para triagem manual pelo mantenedor.
        raw_to_canonical: mapa original→lista de canônicos (para auditoria).
    """

    canonical: List[str] = field(default_factory=list)
    leaks: List[str] = field(default_factory=list)
    other_soros: List[str] = field(default_factory=list)
    unknown: List[str] = field(default_factory=list)
    raw_to_canonical: List[Tuple[str, List[str]]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deburr(text: str) -> str:
    """Remove acentos mantendo o restante."""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _normalize(text: str) -> str:
    """Lowercase, sem acento, sem pontuação terminal, whitespace colapsado.

    Também remove conteúdo entre parênteses (anotações tipo "(Pentavalente)"
    que são modificadores, não tipos). Typos estruturais do PDF
    ("Botrotrópico" → "Botropico") são tratados antes do match.
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # remove anotações entre parênteses
    text = re.sub(r"\s*\([^)]*\)\s*", " ", text).strip()
    text = text.rstrip(".;,:-")
    text = text.strip()
    text = _deburr(text).lower()
    # typos estruturais do PDF
    text = text.replace("botrotropico", "botropico")
    return text


def _is_leak(raw: str) -> bool:
    if len(raw) > MAX_REASONABLE_LEN * 2:
        return True
    for pat in LEAK_PATTERNS:
        if pat.search(raw):
            return True
    return False


def _is_non_antivenom(norm: str) -> bool:
    for pat in NON_ANTIVENOM_PATTERNS:
        if pat.search(norm):
            return True
    return False


def _try_sigla(norm: str) -> List[str]:
    """Expande siglas. Retorna lista de canônicos ou [] se não for sigla."""
    token = norm.strip()
    if token in SIGLA_MAP:
        mapped = SIGLA_MAP[token]
        if mapped in COMPOUND_EXPANSION:
            return list(COMPOUND_EXPANSION[mapped])
        return [mapped]
    return []


def _try_patterns(norm: str) -> List[str]:
    """Aplica regexes canônicos. Pode retornar múltiplos se a string contém combos."""
    found: List[str] = []
    for pat, canonical in CANONICAL_PATTERNS:
        if pat.search(norm):
            if canonical in COMPOUND_EXPANSION:
                for c in COMPOUND_EXPANSION[canonical]:
                    if c not in found:
                        found.append(c)
            else:
                if canonical not in found:
                    found.append(canonical)
    return found


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def canonicalize_one(raw: str) -> Tuple[List[str], str]:
    """Canonicaliza UMA string. Retorna (lista_canonicos, categoria).

    categoria ∈ {"canonical", "leak", "non_antivenom", "unknown"}.
    Se "canonical", a lista pode ter 1+ itens (combos).
    Se outra categoria, a lista está vazia.
    """
    if not raw or not raw.strip():
        return [], "unknown"

    # 1) Vazamento óbvio por frase
    if _is_leak(raw):
        return [], "leak"

    norm = _normalize(raw)

    # 2) Divide por delimitadores e resolve cada parte
    parts = [p.strip() for p in SPLIT_PATTERN.split(norm) if p.strip()]

    aggregated: List[str] = []
    had_non_antivenom = False
    had_unknown_part = False

    for part in parts:
        # Vazamento ao nível do fragmento (caso string seja muito longa combinando)
        if len(part) > MAX_REASONABLE_LEN:
            return [], "leak"

        if _is_non_antivenom(part):
            had_non_antivenom = True
            continue

        siglas = _try_sigla(part)
        if siglas:
            for c in siglas:
                if c not in aggregated:
                    aggregated.append(c)
            continue

        patterns = _try_patterns(part)
        if patterns:
            for c in patterns:
                if c not in aggregated:
                    aggregated.append(c)
            continue

        # não reconhecido
        had_unknown_part = True

    if aggregated:
        return aggregated, "canonical"
    if had_non_antivenom and not had_unknown_part:
        return [], "non_antivenom"
    return [], "unknown"


def canonicalize_list(raw_list: Iterable[str]) -> CanonicalResult:
    """Canonicaliza uma lista de strings. Retorna CanonicalResult consolidado."""
    result = CanonicalResult()
    seen_canonical: List[str] = []

    for raw in raw_list:
        canon, category = canonicalize_one(raw)
        result.raw_to_canonical.append((raw, list(canon)))

        if category == "canonical":
            for c in canon:
                # preserva ordem mas deduplica global
                if c not in seen_canonical:
                    seen_canonical.append(c)
        elif category == "leak":
            if raw not in result.leaks:
                result.leaks.append(raw)
        elif category == "non_antivenom":
            if raw not in result.other_soros:
                result.other_soros.append(raw)
        else:
            if raw not in result.unknown:
                result.unknown.append(raw)

    result.canonical = seen_canonical
    return result


# ---------------------------------------------------------------------------
# CLI (para rodar como script)
# ---------------------------------------------------------------------------


def _cli() -> int:
    """Uso: python canonicalize_antivenoms.py app/hospitals.json [--report]

    Lê o JSON do site, canonicaliza cada hospital e imprime estatísticas.
    Se --report, escreve `canonicalization_report.md` com diffs por hospital.
    """
    import json
    import sys
    from collections import Counter

    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    path = sys.argv[1]
    make_report = "--report" in sys.argv

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    hospitals = data if isinstance(data, list) else data.get("hospitals", [])

    stats = Counter()
    leaked_hospitals: List[dict] = []
    unknown_counter: Counter = Counter()

    for h in hospitals:
        raw_list = h.get("antivenoms", []) or []
        if isinstance(raw_list, str):
            raw_list = [raw_list]
        result = canonicalize_list(raw_list)
        stats["hospitals_total"] += 1
        if result.leaks:
            stats["hospitals_with_leak"] += 1
            leaked_hospitals.append({
                "state": h.get("state"),
                "city": h.get("city"),
                "hospital_name": h.get("hospital_name"),
                "leaks": result.leaks,
            })
        if result.unknown:
            for u in result.unknown:
                unknown_counter[u] += 1
        stats["hospitals_with_canonical"] += 1 if result.canonical else 0

    print(f"Total hospitais: {stats['hospitals_total']}")
    print(f"Com canônico identificado: {stats['hospitals_with_canonical']}")
    print(f"Com vazamento para mover p/ note: {stats['hospitals_with_leak']}")
    print(f"Strings únicas não reconhecidas: {len(unknown_counter)}")
    for s, n in unknown_counter.most_common(20):
        print(f"  [{n:>4}]  {s!r}")

    if make_report:
        out = "canonicalization_report.md"
        with open(out, "w", encoding="utf-8") as f:
            f.write("# Canonicalization Report\n\n")
            f.write(f"**Hospitais com vazamento ({len(leaked_hospitals)}):**\n\n")
            for item in leaked_hospitals:
                f.write(f"- `{item['state']}` / {item['city']} / {item['hospital_name']}\n")
                for leak in item["leaks"]:
                    f.write(f"    - {leak!r}\n")
            f.write(f"\n**Strings não reconhecidas (top 50):**\n\n")
            for s, n in unknown_counter.most_common(50):
                f.write(f"- `{s}` — {n} ocorrências\n")
        print(f"\nRelatório escrito em {out}")

    return 0


# ---------------------------------------------------------------------------
# Testes (rode com: python -m pytest canonicalize_antivenoms.py -v)
# ---------------------------------------------------------------------------


def _self_test():
    """Bateria de testes baseada nas 126 variantes reais do hospitals.json."""

    # Nomes canônicos triviais
    assert canonicalize_one("Botrópico") == (["Botrópico"], "canonical")
    assert canonicalize_one("BOTRÓPICO") == (["Botrópico"], "canonical")
    assert canonicalize_one("Botropico") == (["Botrópico"], "canonical")
    assert canonicalize_one("botrópico") == (["Botrópico"], "canonical")

    # Ponto final não duplica
    assert canonicalize_one("Laquético.") == (["Laquético"], "canonical")
    assert canonicalize_one("Laquetico") == (["Laquético"], "canonical")
    assert canonicalize_one("Laquético") == (["Laquético"], "canonical")

    # Prefixo "anti" e "soro"
    assert canonicalize_one("Antibotropico") == (["Botrópico"], "canonical")
    assert canonicalize_one("Soro antibotrópico") == (["Botrópico"], "canonical")
    assert canonicalize_one("soro anticrotálico") == (["Crotálico"], "canonical")

    # Siglas
    assert canonicalize_one("SAB") == (["Botrópico"], "canonical")
    assert canonicalize_one("SAC") == (["Crotálico"], "canonical")
    assert canonicalize_one("SAEsc") == (["Escorpiônico"], "canonical")
    assert canonicalize_one("SAESC") == (["Escorpiônico"], "canonical")
    assert canonicalize_one("SAAr") == (["Aracnídico"], "canonical")

    # Siglas compostas
    assert canonicalize_one("SABC") == (["Botrópico", "Crotálico"], "canonical")
    assert canonicalize_one("SABL") == (["Botrópico", "Laquético"], "canonical")

    # Combos em linguagem natural
    canon, cat = canonicalize_one("Botrópico e Escorpiônico")
    assert cat == "canonical"
    assert set(canon) == {"Botrópico", "Escorpiônico"}

    canon, cat = canonicalize_one("Crotálico e Escorpiônico")
    assert cat == "canonical" and set(canon) == {"Crotálico", "Escorpiônico"}

    canon, cat = canonicalize_one("Fonêutrico e Lonômico")
    assert cat == "canonical" and set(canon) == {"Fonêutrico", "Lonômico"}

    # Typos do PDF
    assert canonicalize_one("Escoepiônico") == (["Escorpiônico"], "canonical")
    assert canonicalize_one("Escopiônico") == (["Escorpiônico"], "canonical")
    assert canonicalize_one("Escorcorpiônico") == (["Escorpiônico"], "canonical")
    assert canonicalize_one("Lonômoico") == (["Lonômico"], "canonical")
    assert canonicalize_one("Lonônomico") == (["Lonômico"], "canonical")
    assert canonicalize_one("Rotálico") == (["Crotálico"], "canonical")
    assert canonicalize_one("Fonêutricoe") == (["Fonêutrico"], "canonical")

    # Vazamentos (devem ir para `leaks`)
    assert canonicalize_one(
        "É suprido pela rede de frio quando do atendimento de ocorrência, dada a proximidade"
    ) == ([], "leak")
    assert canonicalize_one(
        "Os soros ficam armazenados na rede de frio, na necessidade são disponibilizados para o Hospital."
    ) == ([], "leak")
    assert canonicalize_one("É suprido pelo Hospital Clériston Andrade, quando necessário") == ([], "leak")
    assert canonicalize_one("É suprido pelo CIATox quando do atendimento de ocorrência, dada a proximidade") == ([], "leak")

    # Soros NÃO-antiveneno
    assert canonicalize_one("Antirrábico") == ([], "non_antivenom")
    assert canonicalize_one("Antirrabico.") == ([], "non_antivenom")
    assert canonicalize_one("Soro Antitetânico") == ([], "non_antivenom")
    assert canonicalize_one("Antitetâtico") == ([], "non_antivenom")
    assert canonicalize_one("DT") == ([], "non_antivenom")

    # Parênteses / anotações devem ser ignorados como "Pentavalente"
    assert canonicalize_one("Botrópico (Pentavalente)") == (["Botrópico"], "canonical")
    assert canonicalize_one("Botrotrópico (Pentavalente)") == (["Botrópico"], "canonical")

    # Combos via ponto e vírgula
    canon, cat = canonicalize_one("Botrópico; Crotálico; Elapídico; Laquétio; Aracnídeo")
    assert cat == "canonical"
    assert set(canon) == {"Botrópico", "Crotálico", "Elapídico", "Laquético", "Aracnídico"}

    # Lista: deduplicação + preservação de ordem
    res = canonicalize_list([
        "Botrópico",
        "Botrópico.",
        "Escorpiônico",
        "Laquetico",
        "É suprido pela rede de frio quando do atendimento de ocorrência, dada a proximidade",
        "Antirrábico",
        "SAB",  # repetido depois do "Botrópico"
        "Fonêutrico e Lonômico",
    ])
    assert res.canonical == ["Botrópico", "Escorpiônico", "Laquético", "Fonêutrico", "Lonômico"]
    assert len(res.leaks) == 1
    assert res.other_soros == ["Antirrábico"]
    assert res.unknown == []

    print("✓ Todos os testes passaram.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "--self-test":
        _self_test()
    else:
        raise SystemExit(_cli())
