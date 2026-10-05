"""Group published articles into stories from the command line."""

import sys

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.intelligence.stories.service import build_stories


def main() -> None:
    force = "--force" in sys.argv[1:]
    with Session(get_engine()) as session:
        report = build_stories(session, force=force)
    print(
        f"Considered {report.considered} articles. "
        f"Created {report.created}, attached {report.attached}, stories {report.stories}."
    )


if __name__ == "__main__":
    main()
