# Plan: skill-verification (trust score) scoring

Status: **draft** — the weights/thresholds below need a short experiment against `sample_data/ground_truth.json` (and later a hand-labeled real dataset) before Phase 5 implementation is finalized. This doc is what Phase 5 codes against.

## Goal

For every skill a candidate's pipeline touches, produce one number — the **trust score** — and a flag when the resume's claim and the demonstrated performance disagree.

## Inputs (per skill, per candidate)

| Input | Range | Source |
|---|---|---|
| `resume_claim` | boolean | Was this skill present in `resumes.skills` (Module 6) |
| `test_score` | 0-1, nullable | Average correctness of `test_attempts.answers` entries tagged with this skill (Module 9) |
| `interview_score` | 0-1, nullable | Per-skill score from interview evaluation (Module 11) |

`test_score`/`interview_score` are nullable because a skill might only be probed in one of the two stages, not both — the formula below has to handle that.

## Formula (v1 draft)

```
demonstrated_score =
    if both test_score and interview_score exist:  0.5 * test_score + 0.5 * interview_score
    elif only test_score exists:                    test_score
    elif only interview_score exists:                interview_score
    else:                                             null   # skill was claimed but never actually probed — can't verify yet

trust_score = demonstrated_score   # when demonstrated_score is null, trust_score is null and no flag is set

flag =
    if resume_claim is true and demonstrated_score < 0.4:   "claimed_but_unverified"
    elif resume_claim is false and demonstrated_score > 0.7: "undersold"
    else: null
```

## Worked example — `sample_data/resumes/06_karan_kapoor_inflated_resume.txt`

This resume claims `kubernetes`, `graphql`, `machine learning`, `tensorflow`, `microservices architecture`, `system design`, `kafka` (see `ground_truth.json`) but the experience/project text backing it up is generic and junior. Once this candidate runs through a generated assessment and interview (both of which will tag questions/exchanges against these claimed skills), we'd expect:

- Low `test_score`/`interview_score` on those 7 skills → `demonstrated_score` well under 0.4 → each gets flagged `claimed_but_unverified`.
- Reasonable scores on `python`, `fastapi`, `docker` (skills genuinely reflected in the resume's actual content) → no flag.

This resume is the intended regression test for this feature: **if the pipeline doesn't flag most of those 7 skills, the formula/weights need revisiting before trusting it on real candidates.**

## Open questions to settle before/during Phase 5

1. **Threshold values (0.4 / 0.7 above)** are placeholders — tune them once a few real (or `sample_data`) candidates have run through the full pipeline and you can eyeball whether the flags feel right.
2. **Weighting of test vs. interview** (currently 50/50) — an argument exists for weighting interview higher, since it's harder to fake a live follow-up than a multiple-choice guess. Revisit after the first few real runs.
3. **What happens when a skill is never probed at all** (no test question or interview exchange tagged with it) — current answer: `trust_score` stays null, no flag, it just doesn't appear in the "verified" section of the dashboard. Confirm this is the right UX with the team before Phase 5 frontend work.

## Output shape (feeds `GET /verification/{user_id}`)

```json
[
  {
    "skill_name": "kubernetes",
    "resume_claim": true,
    "test_score": 0.2,
    "interview_score": 0.15,
    "trust_score": 0.175,
    "flag": "claimed_but_unverified"
  }
]
```
