"""Request-local response language. Machine IDs and submitted text are never translated."""

import json
import re
from contextvars import ContextVar
from functools import lru_cache

from smart_recycling.settings import PROJECT_ROOT

request_language: ContextVar[str] = ContextVar("request_language", default="en")


def language_from_header(header: str) -> str:
    preferences = []
    for part in header.split(","):
        tag, _, weight = part.strip().partition(";")
        try:
            quality = float(weight.strip().removeprefix("q=")) if weight else 1.0
        except ValueError:
            continue
        tag = tag.casefold().split("-")[0]
        if tag in {"en", "mk"} and 0 < quality <= 1:
            preferences.append((quality, tag))
    return max(preferences, key=lambda pair: pair[0])[1] if preferences else "en"


@lru_cache
def catalog() -> dict[str, str]:
    return json.loads((PROJECT_ROOT / "web/locales/mk.json").read_text(encoding="utf-8"))


@lru_cache
def templates():
    result = []
    for source, target in catalog().items():
        if not re.search(r"\{\d+\}", source):
            continue
        parts = re.split(r"(\{\d+\})", source)
        fields = [part for part in parts if re.fullmatch(r"\{\d+\}", part)]
        pattern = "".join("(.+?)" if part in fields else re.escape(part) for part in parts)
        result.append((len(source) - sum(map(len, fields)), re.compile(pattern), fields, target))
    return sorted(result, key=lambda item: item[0], reverse=True)


def translate(text: str, language: str | None = None) -> str:
    if (language or request_language.get()) != "mk":
        return text
    translated = catalog().get(text)
    if translated is not None:
        return translated
    for _, pattern, fields, target in templates():
        match = pattern.fullmatch(text)
        if match:
            values = dict(zip(fields, match.groups(), strict=True))
            return re.sub(
                r"\{\d+\}",
                lambda m, values=values: catalog().get(
                    values.get(m[0], m[0]), values.get(m[0], m[0])
                ),
                target,
            )
    return text


def guidance_translation(answer, language: str):
    return answer.model_copy(
        update={
            "message": translate(answer.message, language),
            "clarification_question": translate(answer.clarification_question, language)
            if answer.clarification_question
            else None,
            "choices": [
                choice.model_copy(update={"label": translate(choice.label, language)})
                for choice in answer.choices
            ],
        }
    )
