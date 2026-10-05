"""Write the phone site from the local database."""

import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR
from app.db.database import get_engine
from app.publish.snapshot import SnapshotRefused, publish_snapshot


def main() -> None:
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BACKEND_DIR.parent / "docs"
    try:
        with Session(get_engine()) as session:
            catalog = publish_snapshot(session, destination)
    except SnapshotRefused as exc:
        print(exc)
        sys.exit(1)
    print(f"Published {len(catalog['stories'])} stories to {destination}")


if __name__ == "__main__":
    main()
