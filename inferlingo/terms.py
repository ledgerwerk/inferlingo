"""Natural-language term helpers and deterministic wording unification."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

# A and I are common English words, so they are deliberately not variables.
_VARIABLE_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Z](?:[0-9]+)?)(?![A-Za-z0-9_])")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_'’\-]*")
_NOT_VARIABLES = {"A", "I"}


def is_variable(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Z](?:[0-9]+)?", text)) and text not in _NOT_VARIABLES


def variables_in(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(1) for match in _VARIABLE_RE.finditer(text) if is_variable(match.group(1))))


def replace_variables(text: str, replace) -> str:
    def repl(match: re.Match[str]) -> str:
        value = match.group(1)
        return replace(value) if is_variable(value) else value

    return _VARIABLE_RE.sub(repl, text)


def strip_sentence(text: str) -> str:
    return text.strip().rstrip(".?!").strip()


def normalize(text: str) -> str:
    return " ".join(token.lower() for token in tokenize(strip_sentence(text)))


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def walk(term: str, substitution: Mapping[str, str]) -> str:
    """Follow variable-to-variable bindings until a value or unbound variable is reached."""
    seen: set[str] = set()
    value = term
    while is_variable(value) and value in substitution and value not in seen:
        seen.add(value)
        value = substitution[value]
    return value


def substitute(text: str, substitution: Mapping[str, str]) -> str:
    """Replace variables repeatedly so transitive bindings are resolved."""
    result = text
    for _ in range(32):
        updated = replace_variables(result, lambda variable: walk(variable, substitution))
        if updated == result:
            return updated
        result = updated
    return result


def bind(variable: str, value: str, substitution: dict[str, str]) -> bool:
    """Bind a whole variable to a phrase or another variable, rejecting conflicts."""
    variable = walk(variable, substitution)
    value = substitute(value, substitution).strip()
    if not is_variable(variable):
        return normalize(variable) == normalize(value)
    if value == variable:
        return True
    if is_variable(value):
        other = walk(value, substitution)
        if other == variable:
            return True
        if is_variable(other):
            substitution[variable] = other
            return True
        value = other
    existing = substitution.get(variable)
    if existing is not None:
        return normalize(substitute(existing, substitution)) == normalize(value)
    substitution[variable] = value
    return True


def merge_substitutions(base: Mapping[str, str], extra: Mapping[str, str]) -> dict[str, str] | None:
    merged = dict(base)
    for variable, value in extra.items():
        if not bind(variable, value, merged):
            return None
    # Normalize chains after the merge so solution output is easy to inspect.
    for variable in list(merged):
        merged[variable] = substitute(merged[variable], merged)
    return merged


def _bound_tokens(variable: str, substitution: Mapping[str, str]) -> list[str] | None:
    resolved = walk(variable, substitution)
    if resolved == variable:
        return None
    return tokenize(resolved)


def match_wording(left: str, right: str) -> dict[str, str] | None:
    """Unify equal wording with variables, allowing a variable to stand for a word phrase.

    This intentionally does *not* decide paraphrases. If fixed tokens differ, the semantic unifier
    gets a chance later.
    """
    a = tokenize(strip_sentence(left))
    b = tokenize(strip_sentence(right))

    def rec(i: int, j: int, substitution: dict[str, str]) -> dict[str, str] | None:
        if i == len(a) and j == len(b):
            return substitution
        if i == len(a) or j == len(b):
            return None

        ta = a[i]
        tb = b[j]
        va = is_variable(ta)
        vb = is_variable(tb)

        if not va and not vb:
            if ta.lower() != tb.lower():
                return None
            return rec(i + 1, j + 1, substitution)

        if va and vb:
            trial = dict(substitution)
            if not bind(ta, tb, trial):
                return None
            return rec(i + 1, j + 1, trial)

        if va:
            bound = _bound_tokens(ta, substitution)
            if bound is not None:
                if [x.lower() for x in b[j : j + len(bound)]] != [x.lower() for x in bound]:
                    return None
                return rec(i + 1, j + len(bound), substitution)
            for end in range(j + 1, len(b) + 1):
                span = b[j:end]
                if any(is_variable(token) for token in span):
                    break
                trial = dict(substitution)
                if bind(ta, " ".join(span), trial):
                    found = rec(i + 1, end, trial)
                    if found is not None:
                        return found
            return None

        bound = _bound_tokens(tb, substitution)
        if bound is not None:
            if [x.lower() for x in a[i : i + len(bound)]] != [x.lower() for x in bound]:
                return None
            return rec(i + len(bound), j + 1, substitution)
        for end in range(i + 1, len(a) + 1):
            span = a[i:end]
            if any(is_variable(token) for token in span):
                break
            trial = dict(substitution)
            if bind(tb, " ".join(span), trial):
                found = rec(end, j + 1, trial)
                if found is not None:
                    return found
        return None

    return rec(0, 0, {})


def freshen(text: str, mapping: dict[str, str], next_id) -> str:
    def rename(variable: str) -> str:
        if variable not in mapping:
            mapping[variable] = f"{variable}{next_id()}"
        return mapping[variable]

    return replace_variables(text, rename)


def candidate_phrases(text: str, *, limit: int = 254) -> list[str]:
    """Return deterministic contiguous non-variable word spans usable as Choice criteria."""
    tokens = tokenize(strip_sentence(text))
    phrases: list[str] = []
    seen: set[str] = set()

    # Possessives are useful binding candidates in both forms: ``Lisa's`` and ``Lisa``.
    # The reference interpreter exposes both during alignment.
    for token in tokens:
        lower = token.lower()
        if lower.endswith("'s") or lower.endswith("’s"):
            stem = token[:-2]
            if stem and stem.lower() not in seen and not is_variable(stem):
                seen.add(stem.lower())
                phrases.append(stem)
                if len(phrases) >= limit:
                    return phrases

    for width in range(1, len(tokens) + 1):
        for start in range(0, len(tokens) - width + 1):
            span = tokens[start : start + width]
            if any(is_variable(token) for token in span):
                continue
            phrase = " ".join(span)
            key = phrase.lower()
            if key in seen:
                continue
            seen.add(key)
            phrases.append(phrase)
            if len(phrases) >= limit:
                return phrases
    return phrases


def canonicalize_pair(left: str, right: str) -> tuple[str, str, dict[str, str]]:
    """Canonicalize variable names across a pair and return canonical->original names."""
    original_to_canonical: dict[str, str] = {}
    canonical_to_original: dict[str, str] = {}

    def rename(variable: str) -> str:
        if variable not in original_to_canonical:
            canonical = f"V{len(original_to_canonical)}"
            original_to_canonical[variable] = canonical
            canonical_to_original[canonical] = variable
        return original_to_canonical[variable]

    return replace_variables(left, rename), replace_variables(right, rename), canonical_to_original


def restore_variables(text: str, canonical_to_original: Mapping[str, str]) -> str:
    return replace_variables(text, lambda variable: canonical_to_original.get(variable, variable))


def distinct_variables(texts: Iterable[str]) -> list[str]:
    result: list[str] = []
    for text in texts:
        for variable in variables_in(text):
            if variable not in result:
                result.append(variable)
    return result
