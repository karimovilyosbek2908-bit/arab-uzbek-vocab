"""O'zbek kirill alifbosidan lotin alifbosiga transliteratsiya.

Standart qoidalar:
    ў→o', қ→q, ғ→g', ҳ→h, ш→sh, ч→ch, щ→sh, ц→s, ж→j, х→x, ы→i
    ъ→' (tutuq belgisi), ь→ (tushiriladi)
    я→ya, ю→yu, ё→yo (doim)
    е→ye (so'z boshida), aks holda→e
"""

from __future__ import annotations

_SIMPLE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ч": "ch", "ш": "sh", "щ": "sh", "ц": "s",
    "ы": "i", "э": "e", "ъ": "'", "ь": "",
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}
_SPECIAL = {"е": None, "ё": "yo", "я": "ya", "ю": "yu"}


def _map_char(ch: str, at_word_start: bool) -> str:
    lower = ch.lower()
    if lower in _SPECIAL:
        if lower == "е":
            out = "ye" if at_word_start else "e"
        else:
            out = _SPECIAL[lower]
    elif lower in _SIMPLE:
        out = _SIMPLE[lower]
    else:
        return ch

    if ch.isupper() and out:
        out = out[0].upper() + out[1:]
    return out


def cyrillic_to_latin(text: str) -> str:
    result: list[str] = []
    prev_is_letter = False
    for ch in text:
        is_cyr_letter = ch.lower() in _SIMPLE or ch.lower() in _SPECIAL
        at_word_start = not prev_is_letter
        if is_cyr_letter:
            result.append(_map_char(ch, at_word_start))
        else:
            result.append(ch)
        prev_is_letter = ch.isalpha()
    return "".join(result)


if __name__ == "__main__":
    samples = [
        "ишком, айвон, балкон",
        "Стакан, қадаҳ, пиёла",
        "Ўзбекистон",
        "объект, съезд",
        "фойдаланувчи",
    ]
    for s in samples:
        print(f"{s}  ->  {cyrillic_to_latin(s)}")
