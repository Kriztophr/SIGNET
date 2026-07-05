# Stage 5 Contract — Publish

## Objective
Convert the signed draft into the final publishable artifact, run the preflight checklist, and publish only after the reviewer's explicit approval token.

## Inputs
1. Global identity + stage identity
2. Signed `draft_v1.md`
3. `04_references/publication_target.md`
4. `_shared/references/style_guide.md`

## Load skill modules
- `../../_shared/skills/publishing.md`
- `../../_shared/skills/preflight.md`

## Procedure
1. Copy `draft_v1.md` to `05_artifacts/final.md`. Apply venue-specific transforms (heading levels, image alt text, front matter).
2. Run the preflight checklist and record results in `preflight_checklist.md`. Any FAIL halts the stage.
3. Write a dry-run summary: which endpoint will be called, what payload, what will change externally. Save as `dry_run.md`.
4. Stop. Wait for the human to write `SIGNOFF.md` containing `APPROVE_PUBLISH`.
5. On resume, verify the token exists. If present, execute the publish action. Append the response to `publish_log.md`.
6. Write `PUBLISHED.md`: live URL, published timestamp, content hash of `final.md`.

## Preflight checklist (minimum)
- All inline links resolve (HTTP 200 or 3xx to 200).
- No `[UNVERIFIED]`, `[TO-CONFIRM]`, or `[ASSUMPTION]` markers remain.
- Word count within ±10 % of scope target.
- Title, subtitle, tags, canonical URL, and cover image present per `publication_target.md`.
- Author byline and disclosure statements present.

## Definition of done
- `PUBLISHED.md` exists with a live URL and hash.
- `publish_log.md` shows exactly one successful publish call.
- No FAIL rows remain in `preflight_checklist.md`.

## Failure modes to watch
- Publishing without the `APPROVE_PUBLISH` token — never do this.
- Silently re-publishing after a failure. Always halt and let the human decide.
- Losing citations during venue-specific transforms.
