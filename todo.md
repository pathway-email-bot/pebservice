# PEB Service – Todo

## Future Considerations 🤔

- [ ] **Investigate how we can not be marked as spam**
- [ ] **Share with Tom Kerby**

## UX Fixes

- [ ] **End-to-end email testing** — verify emails are actually being sent and received

## Grading & Rubrics

- [ ] **Review rubric communication** — the grading feels too tough, and it's unclear whether the rubric is being communicated well to students before/during attempts. Are students aware of what they're being evaluated on?
- [ ] **Audit rubric evaluation quality** — assess whether the AI is evaluating rubric criteria fairly and accurately. Are the rubrics themselves correct and reasonable for each scenario?
- [ ] **Golden file regression tests** — save sample student emails, run through grading pipeline, assert score/feedback are reasonable. Catches prompt regressions.

## Scenario Quality

- [ ] **Review each scenario for student success** — scenarios are currently theoretical and may set students up to fail. Go through each scenario and identify gaps, e.g. a scenario references "a report you sent" but the student never actually sent one and has no context. Consider generating simple supporting artifacts (e.g. a 3-line report) in the scenario instructions so students have concrete material to work with.
