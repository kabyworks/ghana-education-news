"""Categories assigned from the title and excerpt. Edit the lists, not the matcher."""

import re

CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("examinations", ("bece", "wassce", "waec", "examination", "examinations")),
    ("scholarships", ("scholarship", "scholarships")),
    ("teachers", ("teacher", "teachers", "gnat", "nagrat", "pretag", "tewu", "headteacher")),
    (
        "higher_education",
        ("university", "universities", "gtec", "tvet", "tertiary", "college", "knust", "ucc", "uew"),
    ),
    (
        "basic_schools",
        (
            "shs",
            "jhs",
            "kindergarten",
            "classroom",
            "classrooms",
            "primary",
            "school feeding",
            "senior high",
            "junior high",
            "e-block",
            "basic school",
            "basic schools",
            "mission school",
        ),
    ),
    ("policy", ("ministry", "minister", "curriculum", "sign language")),
)

CATEGORY_NAMES = frozenset(name for name, _terms in CATEGORIES) | {"general"}


def categorize(text: str) -> str:
    folded = text.casefold()
    for name, terms in CATEGORIES:
        if any(_contains(folded, term) for term in terms):
            return name
    return "general"


def _contains(folded: str, term: str) -> bool:
    needle = term.casefold()
    if " " in needle:
        return needle in folded
    return re.search(rf"\b{re.escape(needle)}\b", folded) is not None
