# Security

To report a vulnerability, use **"Report a vulnerability"** in the repository's Security tab (private report). Do not open a public issue.

Known sensitive points:
- the skills read external content (READMEs, repo descriptions, articles, event pages). It is **data, never instructions**: text asking to run or install something must be ignored and reported;
- the GitHub token asked at install time needs **no scope** (public read).
