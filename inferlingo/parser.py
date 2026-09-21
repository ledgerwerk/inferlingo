"""Quote-aware parser for the deliberately small natural-language rule syntax."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Clause, Literal, Program, Query
from .terms import LexError, sentence_tokens, strip_sentence, variables_in


class ParseError(ValueError):
    """Raised when a program or query cannot be represented by the grammar."""


@dataclass(frozen=True, slots=True)
class SourceLocation:
    source: str | None
    line: int
    column: int | None = None


def _strip_comment(text: str) -> str:
    in_quote = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
            index += 1
            continue
        if char == '"':
            in_quote = True
            index += 1
            continue
        if text.startswith("//", index) or char in {"#", "%"}:
            return text[:index]
        index += 1
    return text


def _split_on_words(text: str, words: set[str]) -> list[str]:
    pieces: list[str] = []
    start = 0
    in_quote = False
    escaped = False
    brace_depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
            index += 1
            continue
        if char == '"':
            in_quote = True
            index += 1
            continue
        if char == "{":
            brace_depth += 1
            index += 1
            continue
        if char == "}" and brace_depth:
            brace_depth -= 1
            index += 1
            continue
        if brace_depth == 0 and (char.isalpha() or char == "_"):
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            word = text[index:end].lower()
            if word in words:
                pieces.append(text[start:index].strip())
                start = end
                index = end
                continue
            index = end
            continue
        index += 1
    pieces.append(text[start:].strip())
    return pieces


def _split_alternatives(text: str) -> list[str]:
    return [part for part in _split_on_words(text, {"or"}) if part]


def _split_conditions(text: str) -> tuple[Literal, ...]:
    pieces: list[str] = []
    for part in _split_on_words(text, {"and"}):
        current = []
        start = 0
        in_quote = False
        escaped = False
        for index, char in enumerate(part):
            if in_quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_quote = False
                continue
            if char == '"':
                in_quote = True
            elif char in ",;":
                current.append(part[start:index].strip())
                start = index + 1
        current.append(part[start:].strip())
        pieces.extend(item for item in current if item)

    literals: list[Literal] = []
    for raw in pieces:
        sentence = strip_sentence(raw)
        if not sentence:
            continue
        negated = False
        match = re.match(r"^not\b\s+", sentence, flags=re.IGNORECASE)
        if match:
            negated = True
            sentence = sentence[match.end() :].strip()
        if not sentence:
            raise ParseError("A negated condition must contain a sentence after 'not'.")
        literals.append(Literal(sentence=sentence, negated=negated))
    if not literals:
        raise ParseError("A rule/query branch contains no conditions.")
    return tuple(literals)


def _split_keyword(text: str, keyword: str) -> tuple[str, str] | None:
    parts = _split_on_words(text, {keyword})
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _rule_parts(text: str) -> tuple[str, str] | None:
    s = strip_sentence(text)
    for keyword in ("then", "if", "when"):
        split = _split_keyword(s, keyword)
        if split is None:
            continue
        left, right = split
        if keyword == "then":
            left = re.sub(r"^(?:if|when)\b\s+", "", left, flags=re.IGNORECASE)
            return right, left
        return left, right
    return None


def _parse_error(message: str, *, source: str | None, line: int, column: int | None = None) -> ParseError:
    location = f"{source or '<memory>'}:{line}"
    if column is not None:
        location += f":{column}"
    return ParseError(f"{location}: {message}")


def _validate_program(clauses: list[Clause], *, source: str | None) -> None:
    for clause in clauses:
        location = f"{source or clause.source or '<memory>'}:{clause.line}"
        head_variables = set(variables_in(clause.head))
        if clause.is_fact:
            if head_variables:
                names = ", ".join(sorted(head_variables))
                raise ParseError(f"{location}: strict mode requires a ground fact; variables: {names}")
            continue
        positive_variables = {
            variable for literal in clause.body if not literal.negated for variable in variables_in(literal.sentence)
        }
        for literal in clause.body:
            if not literal.negated:
                continue
            missing_negative = sorted(set(variables_in(literal.sentence)) - positive_variables)
            if missing_negative:
                names = ", ".join(missing_negative)
                raise ParseError(
                    f"{location}: negative condition variable(s) {names} are not bound by a positive condition"
                )
        missing_head = sorted(head_variables - positive_variables)
        if missing_head:
            names = ", ".join(missing_head)
            raise ParseError(
                f"{location}: rule head variable(s) {names} are not range-restricted by a positive condition"
            )


def _ends_statement(text: str) -> bool:
    in_quote = False
    escaped = False
    for char in text:
        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
        elif char == '"':
            in_quote = True
        elif char == ".":
            return True
    return False


def parse_program(text: str, *, source: str | None = "<memory>", strict: bool = True) -> Program:
    clauses: list[Clause] = []
    statements: list[tuple[int, str]] = []
    pending: list[str] = []
    pending_line = 1
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if not pending:
            pending_line = line_number
        pending.append(line)
        if _ends_statement(line):
            statements.append((pending_line, " ".join(pending)))
            pending = []
    if pending:
        statements.append((pending_line, " ".join(pending)))

    for line_number, line in statements:
        try:
            parts = _rule_parts(line)
            if parts is None:
                head = strip_sentence(line)
                if not head:
                    continue
                sentence_tokens(head)
                clauses.append(Clause(head=head, source=source or line, line=line_number))
                continue

            head, body = parts
            if re.match(r"^not\b", head, flags=re.IGNORECASE):
                raise _parse_error("a rule head cannot start with 'not'", source=source, line=line_number)
            for alternative in _split_alternatives(body):
                literals = _split_conditions(alternative)
                sentence_tokens(head)
                for literal in literals:
                    sentence_tokens(literal.sentence)
                clauses.append(
                    Clause(
                        head=strip_sentence(head),
                        body=literals,
                        source=source or line,
                        line=line_number,
                    )
                )
        except LexError as exc:
            raise _parse_error(str(exc), source=source, line=line_number) from exc
    if strict:
        _validate_program(clauses, source=source)
    if not clauses:
        raise ParseError("The program contains no facts or rules.")
    return Program(tuple(clauses))


def parse_query(text: str, *, source: str | None = "<query>") -> Query:
    try:
        cleaned = strip_sentence(text)
        if not cleaned:
            raise ParseError("The query is empty.")
        alternatives = tuple(_split_conditions(part) for part in _split_alternatives(cleaned))
        return Query(alternatives=alternatives, text=text.strip())
    except LexError as exc:
        raise ParseError(f"{source or '<query>'}: {exc}") from exc
