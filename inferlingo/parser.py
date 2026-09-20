"""Parser for the deliberately small natural-language rule syntax."""

from __future__ import annotations

import re

from .models import Clause, Literal, Program, Query
from .terms import strip_sentence


class ParseError(ValueError):
    """Raised when a program or query cannot be represented by the MVP grammar."""


def _split_alternatives(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s+\bor\b\s+", text, flags=re.IGNORECASE) if part.strip()]


def _split_conditions(text: str) -> tuple[Literal, ...]:
    pieces = re.split(r"\s+\band\b\s+|\s*[,;]\s*", text, flags=re.IGNORECASE)
    literals: list[Literal] = []
    for raw in pieces:
        sentence = strip_sentence(raw)
        if not sentence:
            continue
        negated = bool(re.match(r"^not\s+", sentence, flags=re.IGNORECASE))
        if negated:
            sentence = re.sub(r"^not\s+", "", sentence, count=1, flags=re.IGNORECASE).strip()
        if not sentence:
            raise ParseError("A negated condition must contain a sentence after 'not'.")
        literals.append(Literal(sentence=sentence, negated=negated))
    if not literals:
        raise ParseError("A rule/query branch contains no conditions.")
    return tuple(literals)


def _rule_parts(text: str) -> tuple[str, str] | None:
    s = strip_sentence(text)

    match = re.match(r"^if\s+(.+?)\s+then\s+(.+)$", s, flags=re.IGNORECASE)
    if match:
        return match.group(2).strip(), match.group(1).strip()

    match = re.match(r"^if\s+(.+?)\s*,\s*(.+)$", s, flags=re.IGNORECASE)
    if match:
        return match.group(2).strip(), match.group(1).strip()

    match = re.match(r"^when\s+(.+?)\s*,\s*(.+)$", s, flags=re.IGNORECASE)
    if match:
        return match.group(2).strip(), match.group(1).strip()

    match = re.match(r"^(.+?)\s+then\s+(.+)$", s, flags=re.IGNORECASE)
    if match:
        return match.group(2).strip(), match.group(1).strip()

    match = re.match(r"^(.+?)\s+if\s+(.+)$", s, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    match = re.match(r"^(.+?)\s+when\s+(.+)$", s, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return None


def parse_program(text: str) -> Program:
    clauses: list[Clause] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", "%", "//")):
            continue

        parts = _rule_parts(line)
        if parts is None:
            head = strip_sentence(line)
            if not head:
                continue
            clauses.append(Clause(head=head, source=raw, line=line_number))
            continue

        head, body = parts
        if re.search(r"\s+\bor\b\s+", head, flags=re.IGNORECASE) or re.match(
            r"^not\s+", head, flags=re.IGNORECASE
        ):
            raise ParseError(f"line {line_number}: a rule head cannot contain 'or' or start with 'not'")

        for alternative in _split_alternatives(body):
            clauses.append(
                Clause(
                    head=strip_sentence(head),
                    body=_split_conditions(alternative),
                    source=raw,
                    line=line_number,
                )
            )

    if not clauses:
        raise ParseError("The program contains no facts or rules.")
    return Program(tuple(clauses))


def parse_query(text: str) -> Query:
    cleaned = strip_sentence(text)
    if not cleaned:
        raise ParseError("The query is empty.")
    alternatives = tuple(_split_conditions(part) for part in _split_alternatives(cleaned))
    return Query(alternatives=alternatives, text=text.strip())
