"""Publish a built-in original Edulens360 tip into the local database."""

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.services.original_post import create_original_post

TITLE = "7 exam mistakes that quietly steal students' grades (even when they know the answers)"
SUMMARY = (
    "Common exam-day errors that cost marks even when students know the material, "
    "and how to avoid them."
)
CATEGORY = "examinations"
BODY = """You can study hard and still lose marks for reasons that have nothing to do with how much you know. These are the quiet mistakes that cost students grades every year.

### 1. Misreading the instruction
"Answer any three" does not mean answer all. "Answer question 1 and any other two" means question 1 is compulsory. Read the instruction twice before you start writing.

### 2. Leaving compulsory questions for last
Compulsory questions are often the ones that decide your grade. Do them while your mind is fresh, then move to the optional ones.

### 3. Ignoring command words
List, state, explain, discuss, and compare are not the same job. If the question says explain and you only write a name or one word, you leave marks on the table.

### 4. Skipping workings
In subjects that award method marks, the right final answer with no working can still cost you. Show the steps clearly, even if you are sure of the answer.

### 5. Writing the right answer in the wrong place
A correct response in the wrong section, wrong booklet, or under the wrong question number can score zero. Before you move on, check the question number matches what you are answering.

### 6. Changing a correct answer at the last minute
If you are unsure, leave it. Many students erase a right answer in the final minutes and replace it with a wrong one. Change only when you can prove why the new answer is better.

### 7. Skipping the last 5-minute check
Use the end of the paper to check:
your name and index number
unanswered questions
any question you marked to return to
that every answer is in the right place

### Quick rule for exam day
Know the content, then protect the marks. Read the instruction, follow the command word, show your working, and leave time to check.

Edulens360. Practical tips for Ghana's education community."""


def main() -> None:
    with Session(get_engine()) as session:
        story = create_original_post(
            session,
            title=TITLE,
            summary=SUMMARY,
            body=BODY,
            category=CATEGORY,
        )
    print(f"Created original post story_id={story.id} title={story.title}")


if __name__ == "__main__":
    main()
