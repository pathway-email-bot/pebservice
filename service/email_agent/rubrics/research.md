# Rubric Research — Feb 2025

Research into whether the PEB rubrics align with professional email standards,
employer expectations for entry-level remote workers, and the needs of non-native
English speakers. Conducted to inform rubric v1 improvements.

## Research Queries

1. Professional email writing rubric criteria assessment workplace communication
2. Business email rubric ESL non-native English speakers grading criteria
3. BYU Pathway Worldwide professional email skills curriculum learning outcomes
4. What employers look for in professional email communication entry level remote workers
5. Email etiquette training assessment action-oriented clear call to action workplace
6. Subject line importance professional email grading assessment rubric
7. Rubric design best practices educational assessment clear descriptors scoring criteria
8. Empathy in professional email communication workplace skill assessment
9. BLUF (bottom line up front) email technique remote workers developing countries
10. Cross-cultural email communication rubric global remote work assessment
11. Scenario-specific vs generic rubric criteria email assessment advantages disadvantages
12. AI grading rubric reliability consistency LLM automated email assessment best practices
13. Single point rubric vs analytic rubric student feedback professional writing

---

## Key Findings

### What the original default.json rubric got right
- Covers core dimensions (tone, clarity, structure, professionalism, task completion)
- Simple and digestible (5 criteria — within recommended 3–7 range)
- Aligned with BYU-Pathway learning outcomes
- Scenario-agnostic design builds consistent habits

### Gaps found across sources

| Gap | Details |
|-----|---------|
| **Subject line quality** | Universally cited as essential. BYU-Pathway's own curriculum teaches it explicitly. The default rubric didn't assess it, and reply scenarios pre-filled subjects. |
| **Grammar & readability** | Employers list grammar as a credibility marker. ESL experts recommend a "doesn't distract the reader" threshold rather than perfection. The unused `work_email_quality.json` already had ESL-friendly framing. |
| **Actionable next steps / BLUF** | "Task fulfillment" was too vague — didn't differentiate between burying the ask in paragraph 3 vs. leading with it. BLUF (Bottom Line Up Front) is especially valuable for remote workers with unreliable connectivity. |
| **Audience awareness & empathy** | Adapting to the recipient's perspective is consistently cited as an advanced email skill. Not assessed in either rubric. |
| **Cultural & contextual fit** | Cross-cultural rubrics include avoiding idioms, appropriate formality, and time zone awareness. Only in `work_email_quality.json`. |
| **Rubric description vagueness** | Descriptions like "not too long" are insufficient for consistent AI grading. LLM alignment research shows vague criteria produce unreliable scores. |

### Scoring scale research
- 1–5 is standard for analytic rubrics and gives good granularity
- 1–3 is simpler but may not differentiate enough for growth tracking
- Best practice recommends 3–5 levels; 5 was kept with descriptive labels

### Rubric design: generic + scenario-specific hybrid
- Research supports a consistent generic rubric for foundational skills, supplemented by scenario-specific criteria (the `grading_focus` field)
- Key issue: students couldn't see the `grading_focus` expectations — violates rubric transparency principles
- Fix: "See Rubric" feature in the portal now surfaces both

### AI grading reliability
- Well-defined rubric descriptions improve LLM scoring consistency (59–82% internal consistency vs ~43% for human graders)
- Structured multi-step rubrics with detailed descriptors more closely mimic human judgment
- Human-in-the-loop oversight and bias auditing remain best practices

---

## Changes Made (peb_rubric_v1.json)

Based on this research, the default rubric was replaced with `peb_rubric_v1.json`:

| # | Criterion | What changed |
|---|-----------|-------------|
| 1 | Tone & respect | Expanded description for LLM consistency |
| 2 | Clarity & purpose | Renamed from "Clarity & conciseness"; emphasizes stating purpose early |
| 3 | Structure & formatting | Expanded to include sign-off and paragraph formatting |
| 4 | Professionalism & responsibility | Added proactive solution-offering language |
| 5 | Task fulfillment & actionable next steps | Sharpened to require explicit actions, deadlines, CTAs |
| 6 | Grammar & readability | **NEW** — ESL-friendly "doesn't distract" threshold |
| 7 | Subject line | **NEW** — graded for initiate scenarios; reply scenarios get full marks |

All criteria scored 1–5 (Needs Work → Excellent).
