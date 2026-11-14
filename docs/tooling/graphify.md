# Graphify repository map

Graphify's Codex skill was installed from the official [Graphify-Labs/graphify repository](https://github.com/Graphify-Labs/graphify), branch `v8`. Its documented [CLI package is named graphifyy](https://pypi.org/project/graphifyy/), installed here at version `0.9.108` in the ignored `.local/tools/graphify/` virtual environment. The global skill entrypoint and Codex reference files are installed under the user's Codex skills directory. The skill becomes automatically available on the next turn.

This documentation consolidation used local AST extraction and agent-assisted document extraction. No cloud Graphify account, model API key, credential file, or hosted indexing service was used. `.graphifyignore` excludes environment files, installed dependencies, generated builds, local tools, and graph output.

## Local commands

In PowerShell, run from the repository root:

```powershell
.\.local\tools\graphify\Scripts\graphify.exe query "Docker Compose frontend API ports and documentation contracts"
.\.local\tools\graphify\Scripts\graphify.exe export html
```

Generated navigation files live in ignored `graphify-out/`: `graph.json`, `graph.html`, and `GRAPH_REPORT.md`. They are generated tooling output, not a second authored documentation folder.

## Findings used for consolidation

- The active root contract and original frontend draft differed on development authentication. The backend-updated contract became `docs/frontend-backend-contract.md`. The original was retained under `docs/archive/`.
- Backend startup/verification notes and frontend connection instructions were scattered. Current operation now has one Compose guide and one documentation index.
- Frontend handoffs contained historical claims about an absent backend. They remain history rather than overriding current operation.
- Relative Markdown links were migrated with their documents, and independent link checks protect the new layout.

Graphify is a navigation aid, not proof that every dependency is resolved. The pre-consolidation graph contained 1,392 nodes and 4,483 edges. Its raw extraction diagnostics identified 464 dangling endpoint edges, three self-loops, and 167 same-endpoint edge collapses, including unresolved code references. Documentation changes were checked against the actual files as well as the graph. Generated graph coverage is kept separate from runtime verification claims.

The graph was refreshed after consolidation. Current extraction diagnostics are in generated `graphify-out/.graphify_health.json`. Semantic extraction used the host agents. Their token usage was not exposed by the collaboration tool, so generated zero-token placeholders are unknown accounting, not evidence of zero host-model cost. CLI token-reduction benchmarks are estimates, not measured savings for this task.
