"""paper_extract_v1: structured full-text extraction for paper_ingest runs (ADR-0002).

Runs inside the isolated worker (no network, read-only /input, bounded /output and /tmp).
Input: one document artifact from /input/manifest.json:
  * application/gzip  - arXiv e-print: gzip of a tar archive or of a single .tex file
                        (rarely a PDF)
  * application/x-tar - uncompressed source archive
  * application/pdf   - arXiv PDF fallback or an uploaded PDF
Output (/output):
  * paper.json  - stellaris.paper.v1 structure: sections -> paragraphs with stable IDs/locators
  * paper.txt   - flat UTF-8 text of the same content
  * result.json - worker result (artifacts + warnings; no measurements or claims)

The document is untrusted. Archives are read in memory with member, size, and decompression
limits; no member is written to disk, so links and path traversal have no effect. TeX is never
compiled or executed. PDFs are read with pypdf; there is no OCR. Problems the pipeline can
describe are reported as warnings (DOCUMENT_PARSE_FAILED, NO_TEXT_LAYER, TEXT_TRUNCATED), with
exit code 0, so the backend can report them accurately.
"""

import gzip
import io
import json
import os
import posixpath
import re
import sys
import tarfile

OUTPUT = os.environ.get("STELLARIS_OUTPUT_DIR", "/output")
MANIFEST = os.environ.get("STELLARIS_MANIFEST", "/input/manifest.json")
MAX_DECOMPRESSED = 200 * 1024 * 1024
MAX_MEMBERS = 5000
MAX_TEXT_MEMBER = 8 * 1024 * 1024
MAX_PDF_PAGES = 2000
DEFAULT_MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_INCLUDE_DEPTH = 12
TEXT_EXTENSIONS = (".tex", ".ltx", ".bbl")
SECTION_LEVELS = {"part": 0, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3}


class ParseFailure(Exception):
    pass


# -- helpers ------------------------------------------------------------------------

def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def bounded_gunzip(data: bytes) -> bytes:
    out = io.BytesIO()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as fh:
            while chunk := fh.read(1024 * 1024):
                out.write(chunk)
                if out.tell() > MAX_DECOMPRESSED:
                    raise ParseFailure("The archive expands beyond the decompression limit.")
    except (OSError, EOFError) as exc:
        raise ParseFailure(f"The gzip stream is corrupt ({type(exc).__name__}).")
    return out.getvalue()


def read_tar_texts(data: bytes) -> dict:
    """Return {normalized member path: text} for TeX-like regular files. Nothing touches disk."""
    files, total, seen = {}, 0, set()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            for count, member in enumerate(tar):
                if count >= MAX_MEMBERS:
                    raise ParseFailure("The archive has too many members.")
                raw_name = member.name
                parts = raw_name.split("/") if isinstance(raw_name, str) else []
                if (not raw_name or "\\" in raw_name or raw_name.startswith("/")
                        or ".." in parts or any(ord(c) < 32 for c in raw_name)):
                    raise ParseFailure("The archive contains an unsafe member path.")
                name = posixpath.normpath(raw_name)
                if name in seen:
                    raise ParseFailure("The archive contains duplicate member paths.")
                seen.add(name)
                if not member.isreg():
                    if member.isdir():
                        continue
                    raise ParseFailure("The archive contains a link or special file.")
                total += member.size
                if member.size > MAX_TEXT_MEMBER or total > MAX_DECOMPRESSED:
                    raise ParseFailure("The archive's files exceed the size limit.")
                if not name.lower().endswith(TEXT_EXTENSIONS):
                    continue
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                files[name] = decode_text(fh.read(MAX_TEXT_MEMBER + 1))
    except tarfile.TarError as exc:
        raise ParseFailure(f"The source archive could not be read ({type(exc).__name__}).")
    return files


def is_tar(data: bytes) -> bool:
    return len(data) > 262 and data[257:262] == b"ustar"


def balanced(text: str, start: int, open_ch="{", close_ch="}"):
    """text[start] must be open_ch. Returns (content, index after the closing brace)."""
    depth, i = 0, start
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    return text[start + 1:], len(text)


def command_arg(text: str, name: str):
    m = re.search(r"\\" + name + r"\*?\s*(\[[^\]]*\])?\s*\{", text)
    if not m:
        return None
    return balanced(text, m.end() - 1)[0]


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def clean_inline(text: str) -> str:
    text = re.sub(r"\\label\{[^{}]*\}", "", text)
    text = re.sub(r"\\(?:cite[a-zA-Z]*|citep|citet)\*?(?:\[[^\]]*\])*\{([^{}]*)\}", r"[cite: \1]", text)
    text = re.sub(r"\\(?:eq|auto|c|C)?ref\{([^{}]*)\}", r"[ref: \1]", text)
    for _ in range(3):
        text = re.sub(r"\\(?:emph|textbf|textit|textsc|texttt|textrm|underline|mbox)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:maketitle|centering|noindent|newpage|clearpage|medskip|bigskip|smallskip|vfill|hfill)\b",
                  "", text)
    text = text.replace("~", " ").replace("\x00", "")
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


# -- LaTeX --------------------------------------------------------------------------

def find_main(files: dict) -> str:
    candidates = [n for n, t in files.items() if n.lower().endswith((".tex", ".ltx"))
                  and re.search(r"\\begin\s*\{document\}", strip_comments(t))]
    if not candidates:
        raise ParseFailure("No LaTeX file with \\begin{document} was found.")
    with_class = [n for n in candidates if re.search(r"\\documentclass", strip_comments(files[n]))]
    pool = with_class or candidates
    preferred = [n for n in pool if posixpath.basename(n).lower() in ("main.tex", "ms.tex", "paper.tex")]
    return (preferred or sorted(pool, key=lambda n: (-len(files[n]), n)))[0]


def inline_includes(text: str, files: dict, base_dir: str, warnings: list, depth=0, seen=None) -> str:
    seen = set() if seen is None else seen

    def resolve(name):
        name = name.strip()
        for root in (base_dir, ""):
            for candidate in (name, name + ".tex"):
                path = posixpath.normpath(posixpath.join(root, candidate))
                if path in files:
                    return path
        return None

    def replace(m):
        path = resolve(m.group(2))
        if path is None:
            warnings.append(f"Included file {m.group(2).strip()!r} is not in the source archive.")
            return ""
        if depth >= MAX_INCLUDE_DEPTH or path in seen:
            warnings.append(f"Include of {path!r} skipped (recursion limit or cycle).")
            return ""
        return "\n" + inline_includes(strip_comments(files[path]), files, base_dir, warnings, depth + 1,
                                      seen | {path}) + "\n"

    return re.sub(r"\\(input|include|subfile)\s*\{([^{}]+)\}", replace, text)


def take_environments(body: str, names, handler):
    pattern = re.compile(r"\\begin\s*\{(" + "|".join(re.escape(n) for n in names) + r")\}(.*?)\\end\s*\{\1\}",
                         re.S)
    return pattern.sub(lambda m: handler(m.group(1), m.group(2)), body)


def parse_bibitems(text: str):
    refs = []
    for part in re.split(r"\\bibitem", text)[1:]:
        part = part.lstrip()
        key = None
        if part.startswith("["):
            _, end = balanced(part, 0, "[", "]")
            part = part[end:].lstrip()
        if part.startswith("{"):
            key, end = balanced(part, 0)
            part = part[end:]
        entry = clean_inline(re.sub(r"\\newblock", " ", part))
        entry = re.sub(r"\\end\s*\{thebibliography\}.*", "", entry, flags=re.S).strip()
        if entry:
            refs.append({"key": key.strip() if key else None, "text": entry[:4000]})
    return refs


def extract_latex(files: dict, warnings: list) -> dict:
    main = find_main(files)
    source = inline_includes(strip_comments(files[main]), files, posixpath.dirname(main), warnings)
    preamble, _, rest = re.split(r"(\\begin\s*\{document\})", source, maxsplit=1)
    body = re.split(r"\\end\s*\{document\}", rest, maxsplit=1)[0]
    title = command_arg(preamble, "title") or command_arg(body, "title")
    title = clean_inline(title) if title else None

    abstract = None
    m = re.search(r"\\begin\s*\{abstract\}(.*?)\\end\s*\{abstract\}", body, re.S)
    if m:
        abstract = m.group(1)
        body = body[:m.start()] + body[m.end():]
    else:
        arg = command_arg(body, "abstract")
        if arg:
            abstract = arg

    references = []
    bib = re.search(r"\\begin\s*\{thebibliography\}.*?\\end\s*\{thebibliography\}", body, re.S)
    if bib:
        references = parse_bibitems(bib.group(0))
        body = body[:bib.start()] + body[bib.end():]
    else:
        bbl = [n for n in files if n.lower().endswith(".bbl")]
        base = posixpath.splitext(main)[0] + ".bbl"
        chosen = base if base in files else (bbl[0] if bbl else None)
        if chosen:
            references = parse_bibitems(strip_comments(files[chosen]))
    body = re.sub(r"\\bibliography\{[^{}]*\}|\\bibliographystyle\{[^{}]*\}", "", body)

    def float_env(name, content):
        caption = command_arg(content, "caption")
        label = re.search(r"\\label\{([^{}]*)\}", content)
        if not caption:
            return "\n\n"
        prefix = "Table" if name.startswith("table") else "Figure"
        tag = f" ({label.group(1)})" if label else ""
        return f"\n\n\x00CAPTION{prefix}{tag}: {caption}\n\n"

    body = take_environments(body, ["figure", "figure*", "table", "table*", "wrapfigure", "algorithm"], float_env)

    sections = []
    if abstract and clean_inline(abstract):
        sections.append({"title": "Abstract", "number": None, "level": 1, "locator": "Abstract", "raw": abstract})

    heading = re.compile(r"\\(part|chapter|section|subsection|subsubsection)(\*?)\s*(\[[^\]]*\])?\s*\{|\\appendix\b")
    counters = [0, 0, 0]
    appendix = False
    pos = 0
    current = {"title": "Front matter", "number": None, "level": 1, "locator": "Front matter"}
    for hm in heading.finditer(body):
        if hm.start() < pos:
            continue
        current["raw"] = body[pos:hm.start()]
        sections.append(current)
        if hm.group(0).startswith("\\appendix"):
            appendix, counters = True, [0, 0, 0]
            pos = hm.end()
            current = {"title": "Appendix", "number": None, "level": 1, "locator": "Appendix"}
            continue
        title_raw, end = balanced(body, hm.end() - 1)
        pos = end
        kind, starred = hm.group(1), hm.group(2) == "*"
        level = max(1, SECTION_LEVELS[kind])
        title_text = clean_inline(title_raw) or kind.capitalize()
        number = None
        if not starred:
            counters[level - 1] += 1
            for i in range(level, 3):
                counters[i] = 0
            first = chr(ord("A") + counters[0] - 1) if appendix and counters[0] <= 26 else str(counters[0])
            number = ".".join([first] + [str(c) for c in counters[1:level]])
        current = {"title": title_text, "number": number, "level": level,
                   "locator": f"§{number}" if number else f"§{title_text[:60]}"}
    current["raw"] = body[pos:]
    sections.append(current)

    out = []
    for section in sections:
        paragraphs = []
        for block in re.split(r"\n\s*\n", section.pop("raw")):
            kind = "text"
            if block.strip().startswith("\x00CAPTION"):
                kind, block = "caption", block.strip()[len("\x00CAPTION"):]
            text = clean_inline(block.replace("\n", " "))
            if not text or re.fullmatch(r"(\\[A-Za-z@]+\*?(\{[^{}]*\})*\s*)+", text):
                continue
            paragraphs.append({"kind": kind, "text": text})
        if paragraphs:
            out.append({**section, "paragraphs": paragraphs})
    if not out:
        raise ParseFailure("The LaTeX source contains no extractable text.")
    return {"format": "latex_source", "title": title, "abstract": clean_inline(abstract) if abstract else None,
            "page_count": None, "sections": out, "references": references[:5000]}


# -- PDF ----------------------------------------------------------------------------

def extract_pdf(data: bytes, warnings: list) -> dict:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise ParseFailure("The PDF is encrypted.")
            except Exception:
                raise ParseFailure("The PDF is encrypted.")
        page_count = len(reader.pages)
    except ParseFailure:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise ParseFailure(f"The PDF could not be parsed ({type(exc).__name__}).")
    title = None
    try:
        meta = reader.metadata
        if meta and meta.title and str(meta.title).strip():
            title = str(meta.title).strip()[:1000]
    except Exception:
        pass
    sections = []
    for index in range(min(page_count, MAX_PDF_PAGES)):
        try:
            text = reader.pages[index].extract_text() or ""
        except Exception as exc:  # A single bad page is reported, not fatal.
            warnings.append(f"Page {index + 1} could not be read ({type(exc).__name__}).")
            continue
        blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
        if len(blocks) <= 1 and len(text) > 1500:
            # No blank-line structure: chunk at sentence ends after ~1000 characters.
            blocks, current = [], ""
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                current = f"{current} {sentence}".strip()
                if len(current) >= 1000:
                    blocks.append(current)
                    current = ""
            if current:
                blocks.append(current)
        paragraphs = []
        for block in blocks:
            clean = re.sub(r"-\n(?=[a-z])", "", block)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                paragraphs.append({"kind": "text", "text": clean})
        if paragraphs:
            sections.append({"title": f"Page {index + 1}", "number": None, "level": 1,
                             "locator": f"p. {index + 1}", "paragraphs": paragraphs})
    if page_count > MAX_PDF_PAGES:
        warnings.append(f"Only the first {MAX_PDF_PAGES} of {page_count} pages were read.")
    return {"format": "pdf_text", "title": title, "abstract": None, "page_count": page_count,
            "sections": sections, "references": []}


# -- main ---------------------------------------------------------------------------

def finalize(paper: dict, max_text_bytes: int) -> tuple:
    total, truncated, sections = 0, False, []
    for s_index, section in enumerate(paper["sections"], start=1):
        sid = f"s{s_index}"
        kept = []
        for p_index, para in enumerate(section["paragraphs"], start=1):
            size = len(para["text"].encode("utf-8"))
            if total + size > max_text_bytes:
                truncated = True
                break
            total += size
            kept.append({"id": f"{sid}p{p_index}", "locator": f"{section['locator']} ¶{p_index}",
                         "kind": para["kind"], "text": para["text"]})
        if kept:
            sections.append({"id": sid, "number": section["number"], "title": section["title"],
                             "level": section["level"], "locator": section["locator"], "paragraphs": kept})
        if truncated:
            break
    paper = {"schema": "stellaris.paper.v1", **paper, "sections": sections, "truncated": truncated}
    lines = []
    if paper.get("title"):
        lines += [paper["title"], ""]
    for section in sections:
        same = section["locator"].lstrip("§") == section["title"] or section["locator"].startswith("p. ")
        lines += [section["locator"] if same and section["locator"].startswith("p. ") else
                  section["title"] if same else f"{section['locator']} {section['title']}", ""]
        for para in section["paragraphs"]:
            lines += [f"[{para['locator']}] {para['text']}", ""]
    return paper, "\n".join(lines)


def main() -> int:
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    doc = manifest["inputs"][0]
    max_text = int(manifest.get("parameters", {}).get("max_text_bytes", DEFAULT_MAX_TEXT_BYTES))
    with open(doc["path"], "rb") as fh:
        data = fh.read()
    warnings, notes = [], []
    result = {"measurements": [], "claims": [], "artifacts": [], "warnings": warnings}
    try:
        mime = doc["mime_type"]
        if mime == "application/gzip":
            data = bounded_gunzip(data)
            if is_tar(data):
                paper = extract_latex(read_tar_texts(data), notes)
            elif data.startswith(b"%PDF-"):
                paper = extract_pdf(data, notes)
            else:
                paper = extract_latex({"main.tex": decode_text(data)}, notes)
        elif mime == "application/x-tar":
            paper = extract_latex(read_tar_texts(data), notes)
        elif mime == "application/pdf":
            paper = extract_pdf(data, notes)
        else:
            raise ParseFailure(f"Unsupported document type {mime}.")
    except ParseFailure as exc:
        warnings.append({"code": "DOCUMENT_PARSE_FAILED", "message": str(exc)[:2000]})
        _write_result(result)
        return 0
    if paper["format"] == "pdf_text" and not paper["sections"]:
        warnings.append({"code": "NO_TEXT_LAYER", "message": "The PDF has no extractable text layer; OCR is not "
                                                             "performed."})
        _write_result(result)
        return 0
    paper, flat = finalize(paper, max_text)
    paper["extraction_notes"] = notes[:200]
    if paper["truncated"]:
        warnings.append({"code": "TEXT_TRUNCATED", "message": f"Extracted text was truncated at {max_text} bytes."})
    for note in notes[:20]:
        warnings.append({"code": "EXTRACTION_NOTE", "message": note[:2000]})
    with open(os.path.join(OUTPUT, "paper.json"), "w", encoding="utf-8") as fh:
        json.dump(paper, fh, ensure_ascii=False)
    with open(os.path.join(OUTPUT, "paper.txt"), "w", encoding="utf-8") as fh:
        fh.write(flat)
    parents = [{"input_artifact_id": doc["artifact_id"]}]
    result["artifacts"] = [
        {"local_key": "paper_json", "path": "paper.json", "kind": "document", "origin": "derived",
         "mime_type": "application/json", "parents": parents},
        {"local_key": "paper_txt", "path": "paper.txt", "kind": "document", "origin": "derived",
         "mime_type": "text/plain", "parents": parents},
    ]
    _write_result(result)
    print(f"Extracted {paper['format']}: {len(paper['sections'])} sections, "
          f"{sum(len(s['paragraphs']) for s in paper['sections'])} paragraphs, "
          f"{len(paper['references'])} references, truncated={paper['truncated']}.")
    return 0


def _write_result(result):
    with open(os.path.join(OUTPUT, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh)


if __name__ == "__main__":
    sys.exit(main())
