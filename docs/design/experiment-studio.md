# Experiment studio design

Approved November 14, 2026. This direction supersedes the palette, rounded shelves, navigation presentation, and labels in the earlier [visual desk direction](virtual-desk.md). Scientific contracts, resource identifiers, and existing workflows remain unchanged.

## Identity and shared styles

Stellaris uses a cool industrial graphic studio: aluminum framing, white working surfaces, graphite text, and electric violet for actions and selection. The real experiment recordings, charts, and saved sources provide visual variety. There are no decorative gradients, glowing effects, or metallic textures.

Shared colors live in `frontend/styles/tokens.css`: workspace #F3F4F6, framing #E7E9EE, surface #FFFFFF, text #242630, secondary text #606575, borders #CDD1DA, control borders #858B9B, action #6435C9, action hover #5227AE, selected surface #EDE7FA, and selected text #49229C. Semantic success, warning, and error states retain distinct colors and labels.

Geist Sans carries the interface. Page titles use 28/34px at weight 600, section titles 18/24px, card titles 16/22px, compact content and controls 14/20px, and metadata 12/18px. Reading text uses 16/25px within 72ch. Geist Mono is reserved for code and technical identifiers. Measurements use tabular numerals where appropriate.

Spacing follows a 4px scale. Controls have 6px corners, cards and panels 8px, and dialogs 12px. Working surfaces are flat with 1px borders. Only floating surfaces receive shadows. Hover feedback changes color or border instead of lifting cards. Transitions last 150–180ms and respect reduced motion.

## Navigation and brand

The 224px aluminum sidebar owns primary navigation. Its brand block contains the existing mark, Stellaris wordmark, Experiment studio descriptor, and a short violet rule. The first destinations are Overview, Library, Experiments, and Reports. Connections and Activity follow a spacing break. Current navigation uses both weight and a violet inset marker.

A quiet 56px project utility header holds the project name, archived state, connection state, Assistant, Terminal, and project actions. It does not repeat the destination heading. Pages own their visible h1. Content has 32px desktop padding and 16px mobile padding. Below 768px navigation uses a sheet and the header includes the small brand mark.

Assistant defaults closed for new preferences. Existing preferences remain honored. It docks at 1360px and above when the main content retains 640px after padding. Otherwise it opens in a sheet. Inline inspectors require 1008px of available content for a 640px working area, 24px gap, and 344px inspector. Narrower layouts use sheets.

## Page hierarchy and names

Projects uses a compact heading and a single New project action. Its 1/2/3-column grid follows available widths of below640/640/960px with 20px gaps and 16:10 previews. Evidence is contained without clipping labels. Missing previews show the saved question without duplicating it. The empty state explains how to begin.

Overview presents Question and active work, then Sources, Experiments, Results, Findings, and Reports. Sections use headings and separators rather than enclosing rounded shelves. Sources remain distinct from interpretations. Results remain distinct from findings. Retrieved abstracts are identified as abstracts.

Library has one heading and Add menu, followed by one compact toolbar for View, name search, Collections, Filters, Sort, and overflow actions. Its views are Recent, Sources, Notes, Media & data, Findings, Measurements, and All items. Collection and filter chips appear only when active. Saved collection presentation controls belong in the collection menu. On narrow layouts the toolbar wraps and Sort moves into Filters. Search only searches names.

Experiments retains its gallery, then experiment title and selector with local Plan, Data, Analysis, and Results tabs. Reports preserves its evidence-aware generation flow. Connections shows saved explicit relationships. Activity prioritizes active work and then saved history.

Display names change without changing URLs or API values. The legacy `research`, `materials`, `studio`, `literature`, `desk`, and `inputs` identifiers remain valid. Library collections, saved presentations, inspector deep links, browser Back, recording safeguards, and project-scoped drafts remain supported.

## Verification

See [Experiment studio verification](../verification/experiment-studio.md) for checks actually run. Design intent is not evidence of a successful backend or provider request.
