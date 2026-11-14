# Agent-written report analysis

Status: **Implemented and accepted November 14, 2026.** Report generation now calls
the project's configured LangChain Deep Agent to analyze what happened, alongside
the preserved structured evidence summary. The canonical specification is in
[docs/reports-spec.md](docs/reports-spec.md#required-agent-led-analysis), with
[verification and follow-ups](docs/verification/report-analysis.md).

Explain the experiment, inputs, methods, execution outcome, results, uncertainty,
failures, limitations and supported conclusions. Connect relevant retrieved literature
where useful, and cite the actual runs, measurements, artifacts and sources.

Recorded evidence remains authoritative. Never invent observations, fill missing data,
or present a successful execution as proof that the hypothesis is correct. Clearly
separate measured results, interpretation and unresolved questions.

Keep the existing reproducible evidence summary alongside the agent's narrative, and
save the generated report in Reports and Materials.

## Follow-ups to retain

- [x] Implement agent-written analysis with the existing evidence summary and saved report.
- [ ] Evaluate real generated narratives after model configuration is available.
- [ ] Revisit narrative grounding and citation coverage after live usage. Current
  validation checks structure and resource IDs, while scientific meaning and
  claim-by-claim citation coverage rely on the agent's instructions. A synthetic
  adversarial narrative demonstrated that those checks do not establish correctness.

The user accepted the implementation with these follow-ups. Additional hallucination
guards are not a requirement for this delivery.
