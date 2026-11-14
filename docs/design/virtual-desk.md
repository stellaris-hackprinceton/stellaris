# Visual research desk

The [experiment studio design](experiment-studio.md) supersedes this document's colors, type, radii, shelf framing, and display labels. Its evidence and behavior requirements remain applicable.

Approved November 14, 2026. This layout direction supersedes the paired Research widgets, single-column project home, and 2px panel radii in earlier frontend specifications. It preserves scientific contracts and existing supported workflows.

## Composition

Project home presents a responsive grid of project cards with real saved chart or input-media previews, falling back to the research question. Backends with curated views supply the newest matching chart through a sorted catalog lookup. Older backends use their first matching saved artifact because the artifact list is ascending. This fallback is labelled as saved and does not claim to be latest. Active projects end with a labelled New project tile. Active/Archived filtering, ordering, pagination, and creation behavior remain intact.

Research presents full-width shelves in this order: Literature, Experiments, Measurements and results, Findings, Writing. The question and conditional active-work strip precede the shelves. Cards show actual saved content, provenance, and relevant next actions. Recent previews expand in normal document flow; View all opens the dedicated destination. No freeform positioning or layout persistence is introduced.

Materials and Reports reuse content-specific card presentation. Experiments opens a gallery when no experiment is selected, then the existing Studio task views. Tracker places active work before grouped history. Knowledge graph retains its graph surface and inspector. Chat and terminal remain supporting tools.

## Shared visual rules

Retain the cool-neutral background, white surfaces, graphite text, blue accent, and current fonts. Shelves use 16px radii and 24px padding, cards 12px radii, controls 8px radii, and grids 16px gaps. Card grids use one column below 640px available content width, two from 640px, and three from 960px. Home uses two columns on typical desktops and three on large screens.

Contain scientific charts without cropping labels. Preview images and paused videos represent real artifacts; sources without rendered pages use saved abstract text. Missing previews leave titles and actions usable. Never invent measurements, imply abstracts are full text, or equate successful execution with scientific confirmation.

Quick inspection preserves the desk context. Side inspectors require at least 640px remaining working space; use sheets otherwise. Chat uses a sheet when its rail would leave less than 640px working space. Preserve deep links, focus, drafts, uploaded inputs, and terminal state.

## Interfaces and verification

Use existing project-scoped APIs, cached queries, bounded preview requests, and lazy loading. No new public endpoint, persisted cover, or layout schema is required. Unsupported capabilities retain explanatory fallback views. Archived projects remain readable with creation disabled.

Implementation verification is recorded separately in [Virtual desk verification](../verification/virtual-desk.md). Proposed behavior is not evidence of completed checks.
