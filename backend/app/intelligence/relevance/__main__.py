"""Score stored articles from the command line."""

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.intelligence.relevance.service import score_articles


def main() -> None:
    with Session(get_engine()) as session:
        report = score_articles(session)
    print(
        f"Scored {report.considered} articles. "
        f"Publish {report.publish}, reject {report.reject}, review {report.review}."
    )


if __name__ == "__main__":
    main()
