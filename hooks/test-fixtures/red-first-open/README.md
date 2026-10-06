# Open red-first-check cases (issue #57)

Repro cases from the sixth independent review of `hooks/red-first-check.py` that are left open on purpose (the checker is frozen; see the issue for why). They are **not replayed**: each states the wrong verdict it shows today in its leading comment.

Each file defines `BASE` and `PR` (`{path: text | None | ("symlink", target)}`), the same shape as `../red-first/`. When a case is fixed, add `EXIT`, `EXPECT` and `EXPECT_NOT` and move it into `../red-first/`, where `TestReviewCorpus` replays it.
