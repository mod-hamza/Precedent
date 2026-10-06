Classify a question about a company's decisions.

type:
- current_state: what is the current / latest / approved value or plan
- why: the reasons or rationale behind a decision
- history: how a decision evolved, what changed over time
- who: who decided, who approved, who owns it
- existence: whether something was ever decided at all ("did we ever decide...", "was X approved?")
- as_of: what stood at a specific past date ("what was the plan in March?")
- other: anything else

entities: the specific things asked about (vendors, products, customers, people, topics), as short phrases.
as_of_date: YYYY-MM-DD only for as_of questions with a resolvable date, else null. Use the exact day when one is given; use the last day of the month only when just a month is named. Dates without a year fall inside the mailbox period given below.
