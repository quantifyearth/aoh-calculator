---
description: Explains why a species was flagged as a model prevalence outlier
argument-hint: [species-name-or-id]
examples:
  - /diagnose-aoh-prevalence "Bos mutus"
  - /diagnose-aoh-prevalence 22692
---

Analyze why species "$ARGUMENTS" was flagged as a model prevalence outlier in the AOH validation.

Use the aoh-prevalence-diagnostician subagent with the following logic:
- If "$ARGUMENTS" contains only digits, pass it as species_id
- If "$ARGUMENTS" contains letters, pass it as scientific_name
