"""Tokenization, terms, and deterministic wording unification helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field


class LexError(ValueError):
    """Raised when a sentence contains malformed quoted or named-variable syntax."""


@dataclass(frozen=True, slots=True)
class Variable:
    """A logical variable whose identity is independent of its display name."""

    name: str
    scope: int = 0
    braced: bool = field(default=False, compare=False, hash=False, repr=False)


@dataclass(frozen=True, slots=True)
class Atom:
    value: str
    quoted: bool = False


Token = Atom | Variable
Phrase = tuple[Token, ...]


@dataclass(frozen=True, slots=True)
class Sentence:
    tokens: Phrase
    text: str = ""


# A and I are common English words, so they are deliberately not variables.
_VARIABLE_RE = re.compile(r"[A-Z](?:[0-9]+)?")
_NAMED_VARIABLE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_NOT_VARIABLES = {"A", "I"}


def _is_legacy_variable(value: str) -> bool:
    return bool(_VARIABLE_RE.fullmatch(value)) and value not in _NOT_VARIABLES


def is_variable(text: str) -> bool:
    """Return whether a standalone public token denotes a logical variable."""

    if text.startswith("{") and text.endswith("}"):
        return bool(_NAMED_VARIABLE_RE.fullmatch(text[1:-1]))
    return _is_legacy_variable(text)


def _read_quoted(text: str, start: int) -> tuple[str, int]:
    chars: list[str] = []
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == '"':
            return "".join(chars), index + 1
        if char == "\\":
            if index + 1 >= len(text):
                raise LexError("unterminated escape in quoted atom")
            next_char = text[index + 1]
            if next_char in {'"', "\\"}:
                chars.append(next_char)
            else:
                chars.extend(("\\", next_char))
            index += 2
            continue
        chars.append(char)
        index += 1
    raise LexError("unterminated quoted atom")


def _scan_tokens(text: str, *, scope: int = 0) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        if text[index] == '"':
            value, index = _read_quoted(text, index)
            tokens.append(Atom(value, quoted=True))
            continue
        if text[index] == "{":
            end = text.find("}", index + 1)
            if end < 0:
                raise LexError("unterminated named variable")
            name = text[index + 1 : end]
            if not _NAMED_VARIABLE_RE.fullmatch(name):
                raise LexError(f"invalid named variable: {{{name}}}")
            tokens.append(Variable(name, scope, braced=True))
            index = end + 1
            continue

        start = index
        while index < len(text) and not text[index].isspace() and text[index] not in {'"', "{"}:
            index += 1
        value = text[start:index]
        if not value:
            raise LexError(f"unexpected character {text[index]!r}")
        tokens.append(Variable(value, scope) if _is_legacy_variable(value) else Atom(value))
    return tokens


def sentence_tokens(text: str, *, scope: int = 0) -> Phrase:
    return tuple(_scan_tokens(strip_sentence(text), scope=scope))


def _quote_atom(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_tokens(tokens: Iterable[Token], *, preserve_quotes: bool = True) -> str:
    rendered: list[str] = []
    for token in tokens:
        if isinstance(token, Variable):
            rendered.append("{" + token.name + "}" if token.braced else token.name)
        elif token.quoted and preserve_quotes:
            rendered.append(_quote_atom(token.value))
        else:
            rendered.append(token.value)
    return " ".join(rendered)


def _unquoted_render(tokens: Iterable[Token]) -> str:
    return " ".join(token.name if isinstance(token, Variable) else token.value for token in tokens)


def variables_in(text: str) -> list[str]:
    return list(dict.fromkeys(token.name for token in sentence_tokens(text) if isinstance(token, Variable)))


def replace_variables(text: str, replace) -> str:
    tokens = sentence_tokens(text)
    replaced: list[Token] = []
    for token in tokens:
        if isinstance(token, Variable):
            value = replace(token.name)
            replaced.extend(sentence_tokens(str(value)))
        else:
            replaced.append(token)
    return render_tokens(replaced)


def strip_sentence(text: str) -> str:
    value = text.strip()
    if not value:
        return value
    in_quote = False
    escaped = False
    last_outside = -1
    for index, char in enumerate(value):
        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
        elif char == '"':
            in_quote = True
        elif char in ".?!":
            last_outside = index
    if last_outside == len(value) - 1:
        return value[:-1].rstrip()
    return value


def normalize(text: str) -> str:
    return " ".join(
        (token.name if isinstance(token, Variable) else token.value).lower() for token in sentence_tokens(text)
    )


def tokenize(text: str) -> list[str]:
    """Return logical token values while preserving opaque atom contents."""

    return [token.name if isinstance(token, Variable) else token.value for token in sentence_tokens(text)]


def _resolve_token(token: Token, substitution: Mapping[Variable, Phrase]) -> Phrase:
    if not isinstance(token, Variable) or token not in substitution:
        return (token,)
    value = substitution[token]
    if value == (token,):
        return value
    result: list[Token] = []
    for nested in value:
        result.extend(_resolve_token(nested, substitution))
    return tuple(result)


def substitute_tokens(tokens: Iterable[Token], substitution: Mapping[Variable, Phrase]) -> Phrase:
    result: list[Token] = []
    for token in tokens:
        result.extend(_resolve_token(token, substitution))
    return tuple(result)


def substitute(text: str, substitution: Mapping[str, str]) -> str:
    """Replace public variable names repeatedly so transitive bindings resolve."""

    tokens = sentence_tokens(text)
    internal = {Variable(name): sentence_tokens(value) for name, value in substitution.items()}
    return render_tokens(substitute_tokens(tokens, internal), preserve_quotes=False)


def bind(variable: str, value: str, substitution: dict[str, str]) -> bool:
    """Bind a public variable name to a public phrase without textual corruption."""
    resolved_variable = variable
    while is_variable(resolved_variable) and resolved_variable in substitution:
        resolved_variable = substitution[resolved_variable]
    if not is_variable(resolved_variable):
        return normalize(resolved_variable) == normalize(value)
    resolved_value = substitute(value, substitution)
    existing = substitution.get(resolved_variable)
    if existing is not None:
        return normalize(substitute(existing, substitution)) == normalize(resolved_value)
    substitution[resolved_variable] = resolved_value
    return True


def _bind_token(variable: Variable, value: Phrase, substitution: dict[Variable, Phrase]) -> bool:
    value = substitute_tokens(value, substitution)
    if value == (variable,):
        return True
    existing = substitution.get(variable)
    if existing is not None:
        return _match_token_sequences(existing, value, substitution) is not None
    if variable in value:
        return False
    substitution[variable] = value
    return True


def _match_token_sequences(
    left: Phrase,
    right: Phrase,
    substitution: dict[Variable, Phrase],
) -> dict[Variable, Phrase] | None:
    def rec(i: int, j: int, current: dict[Variable, Phrase]) -> dict[Variable, Phrase] | None:
        if i == len(left) and j == len(right):
            return current
        if i == len(left) or j == len(right):
            return None
        left_token = left[i]
        right_token = right[j]
        left_var = isinstance(left_token, Variable)
        right_var = isinstance(right_token, Variable)
        if not left_var and not right_var:
            if left_token.value.lower() != right_token.value.lower():
                return None
            return rec(i + 1, j + 1, current)
        if left_var and right_var:
            trial = dict(current)
            if not _bind_token(left_token, (right_token,), trial):
                return None
            return rec(i + 1, j + 1, trial)
        if left_var:
            bound = substitute_tokens((left_token,), current)
            if bound != (left_token,):
                return rec(i, j, current | {left_token: bound})
            for end in range(j + 1, len(right) + 1):
                span = right[j:end]
                if any(isinstance(token, Variable) for token in span):
                    break
                trial = dict(current)
                if _bind_token(left_token, span, trial):
                    found = rec(i + 1, end, trial)
                    if found is not None:
                        return found
            return None
        bound = substitute_tokens((right_token,), current)
        if bound != (right_token,):
            return rec(i, j, current | {right_token: bound})
        for end in range(i + 1, len(left) + 1):
            span = left[i:end]
            if any(isinstance(token, Variable) for token in span):
                break
            trial = dict(current)
            if _bind_token(right_token, span, trial):
                found = rec(end, j + 1, trial)
                if found is not None:
                    return found
        return None

    return rec(0, 0, dict(substitution))


def match_sentences(left: Sentence | Phrase, right: Sentence | Phrase) -> dict[Variable, Phrase] | None:
    left_tokens = left.tokens if isinstance(left, Sentence) else tuple(left)
    right_tokens = right.tokens if isinstance(right, Sentence) else tuple(right)
    return _match_token_sequences(left_tokens, right_tokens, {})


def match_wording(left: str, right: str) -> dict[str, str] | None:
    """Unify equal wording with variables, allowing variables to stand for phrases."""

    bindings = match_sentences(sentence_tokens(left), sentence_tokens(right))
    if bindings is None:
        return None
    return {variable.name: _unquoted_render(substitute_tokens(value, bindings)) for variable, value in bindings.items()}


def merge_substitutions(base: Mapping[Variable | str, Phrase | str], extra: Mapping[Variable | str, Phrase | str]):
    """Merge public or internal substitutions, returning the same key/value style."""

    internal: dict[Variable, Phrase] = {}
    for variable, value in base.items():
        key = variable if isinstance(variable, Variable) else Variable(variable)
        internal[key] = value if isinstance(value, tuple) else sentence_tokens(value)
    for variable, value in extra.items():
        key = variable if isinstance(variable, Variable) else Variable(variable)
        phrase = value if isinstance(value, tuple) else sentence_tokens(value)
        if not _bind_token(key, phrase, internal):
            return None
    for key in list(internal):
        internal[key] = substitute_tokens(internal[key], internal)
    if any(isinstance(key, Variable) for key in base) or any(isinstance(key, Variable) for key in extra):
        return internal
    return {key.name: _unquoted_render(value) for key, value in internal.items()}


def freshen(text: str, mapping: dict[str, str], next_id) -> str:
    def rename(variable: str) -> str:
        if variable not in mapping:
            mapping[variable] = f"{variable}{next_id()}"
        return mapping[variable]

    return replace_variables(text, rename)


def candidate_phrases(text: str, *, limit: int = 254) -> list[str]:
    """Return deterministic contiguous non-variable spans usable as Choice criteria."""

    tokens = [token for token in sentence_tokens(text) if isinstance(token, Atom)]
    phrases: list[str] = []
    seen: set[str] = set()
    values = [token.value for token in tokens]
    for token in values:
        lower = token.lower()
        if lower.endswith("'s") or lower.endswith("’s"):
            stem = token[:-2]
            if stem and stem.lower() not in seen:
                seen.add(stem.lower())
                phrases.append(stem)
                if len(phrases) >= limit:
                    return phrases
    for width in range(1, len(values) + 1):
        for start in range(0, len(values) - width + 1):
            phrase = " ".join(values[start : start + width])
            key = phrase.lower()
            if key in seen:
                continue
            seen.add(key)
            phrases.append(phrase)
            if len(phrases) >= limit:
                return phrases
    return phrases


def canonicalize_pair(left: str, right: str) -> tuple[str, str, dict[str, str]]:
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
