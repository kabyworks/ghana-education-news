"""Plain-text excerpts taken from feed descriptions."""

from html.parser import HTMLParser

EXCERPT_LIMIT = 1000


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())


def excerpt_from_html(value: str | None) -> str | None:
    if not value:
        return None
    text = html_to_text(value).strip()
    if not text:
        return None
    return text[:EXCERPT_LIMIT]
