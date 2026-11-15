# Stellaris brag video plan (HackPrinceton F26)

## Where we compete, and what judges score

| Track | What it asks | Stellaris evidence to show |
|---|---|---|
| **Science + Discovery** (main track; scored on Creativity, Utility, Charity, Avidity) | "Projects that turn curiosity into discovery: research accelerators, data models, tools to aid scientific processes and methods." | The whole loop on one real question: literature → experiment → isolated runs → chart → agent-analyzed report. |
| **Best use of deepagents** (LangChain) | "Build a deepagent for any use case." | A LangChain Deep Agent per project, in its own container with persistent scratch. Research tools (arXiv search, full-text read, experiment proposal, code save/execute, materials organization) plus a separate locked-down report agent. |
| **Best Practical AI Innovation** (Amazon): Creativity / Usefulness / Technical / UX at 25% each | Agentic multi-step reasoning, real-world impact, adapts to context and feedback, simple to use. | Runs on Amazon Bedrock (ChatBedrockConverse). The agent plans multi-step work, recovers from rejected outputs, and keeps project context across sessions. |

How each judging criterion maps to the video:
- **Creativity (the "ah-ha"):** an AI that tells you what your evidence *cannot* conclude. The report flags that its own cited paper doesn't support the equation.
- **Utility:** it works end to end on a real 25,000-row dataset, with real numbers on screen.
- **Charity:** reproducible, honest science for students and independent researchers without a lab's tooling.
- **Avidity:** polish, a real build (32 runs and 108 artifacts in one project), and a clear next step.

Rules: the video is at most 2:00 (target 1:58). In-person demos are still required.

## Answers
- **What:** an AI research workspace that takes a question to a reproducible, evidence-backed report.
- **For:** students, independent researchers and scientists without lab infrastructure.
- **Different:** it doesn't just answer. It runs the experiment in isolation, keeps every input and output, and is honest about limits.
- **Best claim (real):** 25,000 people, Pearson r = 0.503, W = −37.46 + 55.06 × H, 13.6% lower prediction error than the baseline. Assessment: "supported for the stated within-sample hypothesis, but not for a universal height–weight law."
- **Visual hook:** scattered research tools collapsing into one workspace, then the real scatter chart.
- **Real UI:** projects, research + Assistant, sources, studio plan, runs, run detail, chart, report, connections graph.
- **Tone:** polished and cinematic, in dark studio mode (violet accent `#a68eff`, Geist / Geist Mono).
- **Caption:** "Ask a question. Stellaris finds the papers, designs the experiment, runs it in isolation, and writes the report, including what the evidence can't prove."

## Storyboard (landscape 1920×1080, 30fps, 118s, captions only)

| # | Time | Scene | On-screen text |
|---|---|---|---|
| 1 | 0–7 | Hook: tool chips (papers, PDFs, notebooks, spreadsheets, scripts, plots, drafts, chatbots) drift and multiply | "Research today is scattered across a dozen tools." → "Nothing connects. Nothing is reproducible." |
| 2 | 7–14 | Chips collapse into the Stellaris mark | "Stellaris" / "From question to discovery." |
| 3 | 14–25 | Projects screen → research screen; the question types into the Assistant composer (not sent) | "Start with a question." |
| 4 | 25–38 | Assistant chat (real messages) → Sources tab | "A LangChain Deep Agent searches arXiv and reads full papers…" / "…and says when an abstract isn't enough." |
| 5 | 38–50 | Studio experiment plan, scrolling | "It designs the experiment and writes the analysis code." |
| 6 | 50–66 | Runs tracker → run detail | "Every run executes in a throwaway container: no network, read-only inputs, every output hashed." / "Rejected output? The agent fixes its code and retries." / count-up "32 runs · 108 artifacts" |
| 7 | 66–78 | The real scatter chart, zooming in on the fit | "Real data. 25,000 people." / "r = 0.503" |
| 8 | 78–96 | Report scroll with callouts | "Hypothesis: supported, within this sample." / "W = −37.46 + 55.06 × H" / "13.6% lower error than the baseline" / "Its own cited paper doesn't support the equation. Stellaris says so." |
| 9 | 96–106 | Connections graph | "Every result traces back to the run, file and paper behind it." |
| 10 | 106–113 | Three cards: LangChain Deep Agents · Amazon Bedrock · Isolated execution | short facts per card |
| 11 | 113–118 | Outro mark | "Stellaris. From question to discovery." / "HackPrinceton F26 · Science & Discovery" |

Transitions: dip through the background between screens, slow push-ins on screenshots, and highlight boxes drawn over the real UI.

## Music
`happy-beats-business-moves-vol-1` (120.19 BPM, 164 s): cuts land on the 0.5 s beat grid, with a 3 s fade at the end. **The track's license is unverified**; check ende.app's terms before uploading publicly, or render with `--no-music`.
