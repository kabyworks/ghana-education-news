"""Load the checked starter sources into the database."""

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.services.source_service import seed_sources


def main() -> None:
    with Session(get_engine()) as session:
        added = seed_sources(session)
    print(f"Added {added} sources")


if __name__ == "__main__":
    main()
