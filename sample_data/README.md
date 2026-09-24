# Sample data

Local development/testing fixtures. Not real people — all names and details are invented.

- `resumes/` — 6 sample resumes as plain text (stand-ins for extracted PDF text, so Phase 2's parser can be developed/tested without needing real PDFs yet). Covers backend, frontend, full-stack, data science, and DevOps profiles.
  - `06_karan_kapoor_inflated_resume.txt` is **deliberately** written with a skills list that isn't backed up by the experience/project sections — use this to test the Module 12 skill-verification trust-score flagging (it should come back with several `claimed_but_unverified` flags once test/interview data exists for it).
- `job_descriptions/` — 5 sample job descriptions matching the resume roles above.
- `ground_truth.json` — hand-labeled expected skills per resume/JD, the best-matching JD for each resume, and which of Karan's skills are inflated. Used by unit tests (Phase 2 onward) and the Phase 6 evaluation/bias-audit experiments — not read by the app itself at runtime.

## Adding real PDF versions later

Once the resume upload endpoint exists (Phase 2), it's worth converting a couple of these into actual PDF files (any of the `.txt` files pasted into a simple Google Doc/Word template and exported as PDF works fine) to test the real upload → PyMuPDF extraction path, not just the parsing logic on raw text.
