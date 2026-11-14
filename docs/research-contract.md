# Full-text paper ingestion

Status: integrated; uploaded-PDF and offline extractor/API checks passed on 2026-11-14. Live arXiv and live agent retrieval were not exercised in this pass. This amends the literature and Source
sections of [the frontend–backend contract](frontend-backend-contract.md); metadata and
abstract retrieval remain unchanged.

The existing project `POST /runs` accepts `kind: "paper_ingest"` and exactly one document
selector: `{ "kind": "paper_ingest", "document": { "arxiv_id": "2401.01234" } }` or
`{ "kind": "paper_ingest", "document": { "artifact_id": "<project PDF artifact>" } }`.
Optional metadata is accepted for uploaded documents. `papers.validate_structure(body)`
validates this shape and `papers.build_snapshot(conn, config, project_id, body,
requested_by_run_id=None)` returns the accepted input and snapshot, including the raw artifact
snapshot (for uploads), exact extractor source/hash/version, limits, and accepted time. The
ordinary run queue and cancellation lifecycle apply.

arXiv retrieval uses fixed HTTPS metadata and e-print endpoints on `export.arxiv.org`, with
redirect host checks and bounded downloads. Metadata responses are capped at 1 MiB; e-prints
at 50 MiB. Only fetched material is saved. The downloaded
e-print is retained as an immutable document artifact. Uploaded PDFs are existing immutable
artifacts. The isolated networkless worker parses PDF or LaTeX source; it never compiles or
executes TeX and does not perform OCR. Archive traversal, links, special entries, duplicate
paths, member counts, expansion and output sizes are bounded/rejected. PDF extraction can
fail for malformed, encrypted, text-layer-free, or poorly ordered documents.

Extractor limits: 5,000 archive entries; 8 MiB per file; 200 MiB decompressed archive;
2 MiB normalized extracted text; 16 MiB structured JSON; 2,000 PDF pages. Extraction is
best-effort and may omit unsupported markup, equations, figures, and references.

Success publishes structured `paper.json` and UTF-8 `paper.txt` artifacts, plus an immutable
Source with `retrieval_status: "full_text_retrieved"`, `document_artifact_id`, and additive
`full_text: {format, text_artifact_id, ingest_run_id, section_count, page_count, truncated,
license_url}`. `paper.json` has `schema`, `format`, `title`, `abstract`, `page_count`, `sections`,
`references`, `truncated`, and `extraction_notes`. Sections carry stable IDs, number/title/
level, locator, and paragraphs; paragraphs carry stable IDs, locator, kind, and exact text.
Citation checks validate excerpts and locators against persisted extracted text. Abstract-only
citation behavior remains unchanged. Failed extraction never represents full text as retrieved.

Research-agent context may include bounded persisted papers. `read_paper` and `search_paper`
operate on supplied full text with exact paragraph locators. `request_full_text` is an explicit
agent tool; it performs a bounded ingestion inline (without waiting in the ordinary run queue),
then supplies the retrieved text to the reader/search tools. It can take several minutes and
is limited to two requests per agent run. Project-scoped IDs are not an authorization
boundary. No paid model call is part of ingestion.

Parser API reference: [pypdf PdfReader documentation](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html). The worker pins pypdf 7.0.1.
