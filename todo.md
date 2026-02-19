# PEB Service – Todo

## Future Considerations 🤔

- [ ] **Investigate how we can not be marked as spam**
- [ ] **Share with Tom Kerby**
- [ ] **Consider cold-start warm-up between functions** — when `send_magic_link` runs (student logging in), it could ping `start_scenario` to warm it up since the student will use it next. Options: cross-function ping, Cloud Scheduler during class hours, or `--min-instances=1`. Tradeoff is complexity vs ~3s savings for the first student.


## Housekeeping

- [ ] **Clean up design documents and markdown files** — consolidate, reorganize, and update all `design_docs/` and root-level `.md` files for accuracy. Remove stale/outdated content (e.g. `todo_today.md` dated Feb 6, old implementation plans that are now completed). Ensure remaining docs reflect the current architecture.

## Scenario Quality

- [ ] **Review each scenario for student success** — scenarios are currently theoretical and may set students up to fail. Go through each scenario and identify gaps, e.g. a scenario references "a report you sent" but the student never actually sent one and has no context. Consider generating simple supporting artifacts (e.g. a 3-line report) in the scenario instructions so students have concrete material to work with.
