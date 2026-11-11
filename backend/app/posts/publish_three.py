"""Publish today's three SEO tip posts."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.publish.snapshot import publish_snapshot
from app.services.original_post import create_original_post

POSTS = [
    {
        "title": "How to answer WASSCE essay questions to score more marks",
        "summary": "A simple WASSCE essay method: read the command word, plan fast, answer directly, and use examples so examiners can award more marks.",
        "category": "examinations",
        "image": "https://edulens360.com/images/tips/wassce-essay.png",
        "body": """WASSCE essay marks are often lost on structure, not on knowledge. Use this method so your answers are easier for the examiner to score.

### Read the question twice before you write
Circle the command word: explain, discuss, compare, examine, outline. Those words decide how deep your answer should go. If the question has two parts, plan both before you start.

### Make a short plan in 2 to 3 minutes
Write 4 to 6 points in the margin. Put your strongest points first. A short plan stops you from wandering and running out of time.

### Use a clear paragraph pattern
For each main point:
State the point in one sentence
Explain it
Give an example or reason
Link it back to the question

Examiners reward answers that stay on the question from start to finish.

### Open with a direct answer
Your first paragraph should show you understood the question. Do not spend half a page defining every word. Define only what is needed, then move into your points.

### Use examples from Ghana or your subject
A local, subject-based example is stronger than a vague statement. In Government, History, Social Studies, Economics, and similar papers, specific examples raise your mark.

### Watch your time
If the paper has more than one essay, leave enough time for each. A complete second essay usually beats a perfect first essay and an empty second one.

### Leave 5 minutes to check
Check spelling of key terms, paragraphing, and whether every paragraph answers the question asked.

### Quick rule
Plan, answer directly, explain with examples, and protect your time.

Edulens360. Practical tips for Ghana's education community.""",
    },
    {
        "title": "GES promotion interview questions teachers should prepare for",
        "summary": "Common GES promotion interview themes, sample questions, and how to answer with clear classroom examples instead of long theory.",
        "category": "teachers",
        "image": "https://edulens360.com/images/tips/ges-promotion.png",
        "body": """GES promotion interviews often repeat the same themes. Prepare short, clear answers so you do not freeze when the panel asks.

### Questions about your teaching practice
How do you plan a lesson for mixed-ability learners?
How do you handle a class that is noisy or off-task?
How do you assess learning during and after a lesson?
How do you support learners who are falling behind?

Use one real classroom example for each answer.

### Questions about the profession and GES
Why do you want this promotion?
What does a professional teacher do outside the classroom?
How do you work with your headteacher and colleagues?
How do you handle parent concerns?

Keep answers honest and practical. Avoid long speeches.

### Questions about current education issues
Be ready to talk briefly about:
Free SHS and classroom realities
Continuous professional development
Learner discipline and child protection
Inclusive education
Use of teaching and learning materials

You do not need perfect policy language. Show that you understand what the issue means in a real school.

### Questions that test judgment
What would you do if a colleague was mistreating a learner?
How would you respond if a parent accused you unfairly?
What would you change in your school if given the chance?

Panels look for calm judgment, fairness, and professionalism.

### How to prepare the day before
Write 6 to 8 short stories from your own teaching
Practice answering out loud in 1 to 2 minutes each
Prepare one strength, one improvement area, and one achievement
Carry your documents neatly and arrive early

### Quick rule
Clear example beats long theory. Speak like a classroom teacher who solves problems.

Edulens360. Practical tips for Ghana's education community.""",
    },
    {
        "title": "CSSPS school placement: what to do if you are not satisfied",
        "summary": "What students and parents should do after an unwanted CSSPS placement, including confirmation, official options, and mistakes to avoid.",
        "category": "basic_schools",
        "image": "https://edulens360.com/images/tips/cssps-placement.png",
        "body": """If your CSSPS placement is not what you wanted, act quickly and follow the official process. Panic and random transfers usually waste time.

### First, confirm your placement details
Check:
The school name
Boarding or day status
Programme placed
Your raw score and choices

Take a clear screenshot or printout before you do anything else.

### Understand why the placement happened
Common reasons include:
Your aggregate did not meet the school's cutoff
Your preferred programmes were full
You placed a highly competitive school too high with a weak aggregate
Day or boarding options did not match availability

Knowing the reason helps you choose a realistic next step.

### Use the self-placement or protocol options when available
When CSSPS opens self-placement or related options:
Log in with the correct credentials
Look for schools that still have vacancies
Choose a school and programme you can realistically accept
Save confirmation evidence

Do not wait until the last hours of the window.

### Contact the right office, not only social media
If you need help, start with:
Your junior high school
The district education office
The official CSSPS support channels published for that year

Bring your placement printout, results, and ID details.

### Decide fast between waiting and moving on
Ask:
Can this school still help me reach my next goal?
Is there a vacant school with a better fit?
Will delaying enrolment cost me the academic year?

A good available school is often better than waiting endlessly for a school with no space.

### Avoid these mistakes
Paying someone who promises a guaranteed school
Ignoring enrolment deadlines at the placed school
Changing decisions every day without checking vacancies
Relying only on WhatsApp rumours

### Quick rule
Confirm the placement, use the official window, keep evidence, and choose the best realistic option on time.

Edulens360. Practical tips for Ghana's education community.""",
    },
]


def main() -> None:
    now = datetime.now(timezone.utc)
    created = []
    with Session(get_engine()) as session:
        for index, post in enumerate(POSTS):
            # Keep draft order near the top: WASSCE newest, then GES, then CSSPS.
            when = now - timedelta(seconds=index * 45)
            story = create_original_post(
                session,
                title=post["title"],
                summary=post["summary"],
                body=post["body"],
                category=post["category"],
                published_at=when,
                image_url=post["image"],
            )
            created.append((story.id, story.title))
        catalog = publish_snapshot(session, Path(__file__).resolve().parents[3] / "docs")
    for story_id, title in created:
        print(f"created story_id={story_id} title={title}")
    print(f"published {len(catalog['stories'])} stories")
    print("top3", [(s["id"], s["title"][:48], s.get("image_url")) for s in catalog["stories"][:3]])


if __name__ == "__main__":
    main()
