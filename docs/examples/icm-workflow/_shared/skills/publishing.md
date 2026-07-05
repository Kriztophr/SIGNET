# Skill — Publishing

## When to load
Stage 5, before touching `final.md`.

## Venue-specific transforms
Read `04_references/publication_target.md`. Apply only the transforms listed there; do not invent conventions.

Common transforms:
- Add front matter block (title, excerpt, tags, canonical, feature image, feature image alt).
- Shift heading levels if the venue reserves H1 for the platform.
- Convert relative asset paths to absolute URLs.
- Ensure image alt text is present for every image (accessibility requirement).

## Dry-run first
Before the publish action, write `dry_run.md` describing:
- Endpoint / API called
- Payload summary (title, tag list, canonical URL, hash of body)
- Idempotency key or slug
- Expected external side effects (new URL, RSS entry, email send)

The dry run is the last artifact the human reviews before granting `APPROVE_PUBLISH`.

## Publish action
- Execute exactly once.
- Capture the full response into `publish_log.md` including status code, response body, and server timestamp.
- Compute a SHA-256 of `final.md` and record it in `PUBLISHED.md`. This is the immutable receipt.

## Rollback stance
If the publish call fails or returns a non-2xx response, halt and write `HALT.md`. Do not retry. Let the human decide whether to retry, edit, or cancel.
