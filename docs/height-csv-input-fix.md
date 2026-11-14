# Heights CSV execution fix

Fixed November 14, 2026.

Materials listing exposed catalog `fil_` IDs but execution requires immutable `art_` IDs.
Agent context also treated message attachments as the only usable files. Consequently,
SOCR-HeightWeight.csv was discoverable but never became a worker input.

- Project context now includes a bounded artifact index; Materials tools return actual
  artifact IDs. A chat attachment is no longer required for a project-owned input.
- Execution saves explicitly selected inputs on the experiment with revision checks,
  then freezes its ordinary immutable run snapshot. Project isolation is retained.
- Corrected the saved heights script's stale catalog ID and invalid result enum values,
  preserving previous code versions. Tabular metric values use declared source units
  and conversion assumptions; camera/video scale requirements remain unchanged.

Provider-free verification on the actual uploaded CSV:

- Run: `run_6c4196ff635f42a6aa1201b9a112011e` — succeeded.
- 25,000 rows; two valid measurements, one claim, two output datasets.
- Mean height: 1.72702508535872 m; unweighted descriptive sample result.
- Outputs: height_summary.csv and schema_audit.csv, available in Materials.
- No sex, age or survey-weight fields; no national or sex-specific estimate claimed.
- Python compilation and diff checks passed. No paid model request was made.
