> Ported reference ADR. Verification statements below describe the source branch; current integration checks are recorded separately.

# ADR-0002: Full-text paper ingestion: arXiv LaTeX source first, uploaded PDFs, isolated extraction

Status: Accepted; implemented and verified (scripts/paper_ingest_test.py, 33 checks, 2026-11-14)
Date: 2026-11-14

## Context

The research agent only retrieves arXiv metadata and abstracts (`search_arxiv` in
`backend/project_runtime/agent_runner.py`). The contract already defines
`Source.retrieval_status: "full_text_retrieved"` and `Source.document_artifact_id`, but nothing
produces them, and `application/pdf` is not an accepted upload type. The user wants the agent to
understand whole papers, from **arXiv and from uploaded PDFs**, and prefers **LaTeX source** because
it is easier to analyse as text.

## Decision

1. **New run kind `paper_ingest`.** It turns one document into a new, immutable Source snapshot with
   full text. Inputs: `{ arxiv_id }` or `{ artifact_id }` (an uploaded PDF), plus optional user
   metadata. A user can submit it through `POST /runs`, or the agent can request it through a tool.
2. **arXiv retrieval order.** The primary backend, not the project container, fetches
   `https://export.arxiv.org/e-print/<id>`. This is bounded (≤ 50 MiB, with a host allowlist and a
   redirect check). The result is classified by its bytes:
   - gzip/tar LaTeX source → `latex_source` extraction;
   - PDF (no source available) → `pdf_text` extraction;
   - anything else, or withdrawn → `FULL_TEXT_UNAVAILABLE`, and the source stays abstract-only.

   The raw download is stored as an immutable `reference` artifact (`Source.document_artifact_id`).
3. **Extraction runs in the isolated worker** (new internal pipeline `paper_extract_v1`): no network,
   the usual limits, and output checked by the usual validator. The documents are untrusted
   (archive bombs, path traversal, parser bugs), and the project container holds model credentials
   during agent runs.
   - **LaTeX:** safe tar extraction (no links, no absolute or `..` paths, member/size caps). Find the
     main file (`\documentclass` + `\begin{document}`) and inline `\input`/`\include` only from inside
     the archive. Strip comments. Split on `\section`/`\subsection`/`\subsubsection`/`\appendix`. Keep
     math as LaTeX. Collect `abstract`, figure/table captions with `\label`s, labelled equations, and
     `.bbl`/`\bibitem` references. **TeX is never compiled or executed** (`\write18` risk).
   - **PDF:** `pypdf` (BSD-licensed; PyMuPDF rejected over AGPL) per-page text. Locators are page
     numbers. No OCR: a PDF without a text layer fails with `NO_TEXT_LAYER`. Encrypted or malformed
     PDFs fail with `DOCUMENT_PARSE_FAILED`.
   - Output is a `paper.json` artifact (`application/json`, kind `document`, origin `derived`) with
     stable paragraph IDs and locators (`§3.2 ¶4`, `p. 5`), plus a flat-text artifact. Text over
     2 MiB per paper is truncated, and the truncation is recorded as a warning.
4. **Uploaded PDFs.** `application/pdf` becomes an upload type (kind `document`, origin `reference`).
   At upload, the API only checks the `%PDF-` header and size limits. All parsing happens in the
   worker. A PDF is always downloaded as an attachment and is never shown inline in the app origin.
   The resulting Source uses `provider: "manual"`. PDF-embedded metadata is untrusted and is used
   only when the user supplies none.
5. **Agent access.**
   - Tools `read_paper(source_id, section?)` and `search_paper(source_id, query)` run over `paper.json`
     inside the agent runtime. Search uses keyword (BM25) ranking over paragraphs; no embedding
     service.
   - Papers reach the agent through the agent run's request snapshot. This is the existing
     `_artifact_text_context` path with its own paper budget, so the snapshot records exactly which
     text the model saw.
   - Tool `request_full_text(arxiv_id)` lets the agent ingest during a turn. The backend executes
     that ingestion **inline in the agent run's handler thread** (still a recorded `paper_ingest`
     run, linked to the agent run). It does not go through the run queue, which avoids deadlocking
     on `max_concurrent_runs`. The extracted paper is delivered into the agent's per-run directory
     with `put_archive`, and the tool waits a bounded time for it.
6. **Citation trust.** For a full-text source, a citation's `excerpt` must be a verbatim substring
   of the stored extracted text, compared after whitespace normalisation. A non-null `locator` must
   match a paragraph or page in `paper.json`. Abstract-only sources keep the existing
   abstract-substring rule.
7. **Honesty.** The agent prompt and reports distinguish *abstract-only* from *full text read*.
   Truncated or partly extracted papers say so. Figures are not interpreted in this iteration:
   captions are text, and images are not sent to the model.

## Consequences

- Source snapshots stay immutable. Ingesting creates a new snapshot, and earlier report citations
  are unchanged.
- The worker image adds a pinned `pypdf`. Generated artifact types add `application/gzip` and
  `application/x-tar` (the raw e-print) and `application/pdf`.
- Storing arXiv full text inside a private project is treated as personal research use. The arXiv
  licence URL is recorded when the metadata provides it, and reports quote excerpts only.
- Mathematical content is preserved best when LaTeX source exists. PDF-only papers lose equation
  structure, and their citations use page locators.

## Alternatives considered

- **arXiv HTML (LaTeXML):** good structure, but not available for every paper, and it is a second
  parser. Possible later fallback between LaTeX and PDF.
- **GROBID / Docling / marker:** better PDF structure, but heavy services or ML models. Rejected for
  the hackathon.
- **Parsing in the project container:** simpler plumbing, but untrusted parsing would sit next to
  model credentials. Rejected.
- **Embedding retrieval:** needs an extra model or service and a vector store. BM25 is enough at
  paper scale.
