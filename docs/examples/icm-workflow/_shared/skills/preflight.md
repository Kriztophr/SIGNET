# Skill — Preflight checklist

## When to load
Stage 5, before publishing.

## Checklist rows
Each row in `preflight_checklist.md` uses `PASS`, `FAIL`, or `N/A`. Any `FAIL` halts the stage.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | All inline links resolve to 2xx | HEAD/GET each link; log status |
| 2 | No `[UNVERIFIED]`, `[TO-CONFIRM]`, `[ASSUMPTION]` in body | grep the draft |
| 3 | Word count within ±10 % of target | Programmatic count vs scope brief |
| 4 | All required front-matter fields present | Compare against `publication_target.md` |
| 5 | Feature image meets spec (size, weight, alt) | Read image metadata; verify alt text |
| 6 | Author byline present | Grep for byline pattern |
| 7 | Disclosure statements present (if required) | Compare against venue policy |
| 8 | Canonical URL set correctly | Verify against publication_target policy |
| 9 | Tags all in allowlist | Diff draft tags against allowlist |
| 10 | Content hash captured | Compute SHA-256 of `final.md` |

## Reporting
`preflight_checklist.md` renders as a table with columns: `#`, `Check`, `Result`, `Evidence` (link or grep output). Include a summary line at the bottom: `PASS: X, FAIL: Y, N/A: Z`.
