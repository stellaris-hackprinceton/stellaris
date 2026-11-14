# Materials curated views specification

The [continuous studio direction](design/continuous-studio-direction.md) and its
preferred visual reference govern the next light/dark theme work, ahead of the
historical visual dimensions in this document.

The approved [experiment studio design](design/experiment-studio.md) supersedes visual styles, navigation presentation, and display labels in this specification. Resource identifiers, scientific semantics, and capability requirements remain unchanged.


Version: **1.0 proposed**. Prepared November 14, 2026.
Status: **Curated views are implemented.** This specification remains the behavior reference; card styling uses 12px corners, 16px padding, and shared desk spacing. Video cards render the saved video with controls and no autoplay.

This document defines the replacement browsing experience. Shared colors, typography, card dimensions, and widget states come from [Research desk](research-workspace-spec.md). Proposed wire fields and migration requirements live in the [file workspace contract extension](file-workspace-contract.md#16-proposed-curated-views-extension).

## 1. Interaction model

Materials offers useful presentations of the project's records before asking the researcher to search or configure filters. A material may appear in several views and collections. These are references to one catalog identity, not copies or folders. Changing presentation never changes provenance or makes a note into evidence.

The page begins with the Materials title and actions. Below it, show a labelled **View** selector with Desk, Literature, Notes, Media & data, Findings, Measurements, and All materials. On wider screens use wrapping text tabs. Below 800px of content width use a native labelled select with the same options. No horizontal tab scroller is required.

Place a **Collections** disclosure below the selector. It lists named collections and a New collection action. Selecting one keeps the view selector visible and adds a collection chip with a Clear action. The main heading changes to the collection name, with its description below. The user can change presentation without changing collection membership.

The next line contains **Search names in this view**, Sort, and a compact Filters disclosure. Show applied tag/status filters as removable chips. Search means the existing case-insensitive name substring search. Do not promise passage, abstract, or note-content matching. Secondary tools for tags, membership, and trash remain in All materials.

Typing search waits 250ms before replacing URL state and querying. Switching the view or collection creates a history entry. Opening an inspector creates another entry. Replacing a search string does not create one history entry per character. Clear incompatible selection when a new view excludes it, except explicitly linked files as described in section 5.

## 2. Layout and common controls

The page uses a full-width center surface, up to 1440px, with 16px widget gaps and 12px card gaps. Use the research specification's card grid and 240px minimum card width. Name, record type, and preview lead the card. Technical fields such as byte size and hashes stay in the inspector or All materials.

With at least 1100px available, an open inspector occupies 360px beside a content region of at least 640px, separated by 16px. Below that use a dismissible sheet. An inspector does not replace the entire browse view. Results and experiment editors still open their established routes.

Full-view lists fetch 24 items initially and add 24 on **Load more**. No infinite-scroll trigger is required. Counts use exact backend values only when their scope matches the current query. Otherwise show “24 loaded · more available.” An empty filtered result offers Clear filters. An empty underlying view describes its relevant creation or analysis action.

Cards have separate inspect, open-workflow, and selection controls. Bulk selection is available in All materials only. Preserve existing note immutability rules, archive restrictions, ETags, and command retries.

## 3. Curated view definitions

### Desk

Default on `/materials` with no view parameter. This is a mixed reading surface, not another filtered file table.

- Full-width **Recently added** widget: six newest active files as type-aware cards, expanded to twelve. User metadata edits do not reorder this list.
- Two equal columns beneath it: **Recent notes**, three notes ordered by `updated_at` descending, and **Collections**, six named collection shortcuts in name order. These stack below 800px.
- A final compact shortcut row opens Literature, Media & data, Findings, Measurements, Reports, or All materials.
- The header's **New note** action opens the existing note form in the inspector/sheet. **Add source** opens manual entry. These never become a generic “Add evidence” command.
- Search, tag, status, and collection constraints apply to the material widgets. Collection shortcuts are navigation, not matching material results, and are labelled accordingly.

Mixed-card rendering uses authoritative type: source → citation card, claim → finding card, experiment → compact plan card, measurement set → run/sample card, artifact → kind-specific card, note → prose card, terminal run → execution summary. A report card opens Reports. An unrecognized future type renders a neutral named card with an inspector action.

### Literature

Include only `origin_type=source`, default `created_at desc`. Use the source cards defined by the research specification, without its nine-card overview cap. The view has **Add source** and **Find literature in Chat** actions. Add source stays available when a search matches nothing.

The inspector shows complete citation metadata, retrieval status/date, saved abstract, available document, and recorded citation relationships. Follow the [Literature widget ingestion and reader requirements](research-workspace-spec.md#4-literature-widget) for the Add source action menu, PDF/arXiv extraction, structured sections, citation locators, truncation warnings, original downloads, and ingestion-run links. Provider badges reflect actual records. Never fill an abstract excerpt with generated prose or display a fabricated paper cover.

Raw PDFs/arXiv archives and derived `paper.json`/`paper.txt` are linked attachments of the Source reading experience, while retaining their independent catalog identities. Extractor code, logs, and provenance remain inspectable in All materials and through the producing run. Do not classify documents as images/datasets to force them into Media & data. Failed ingestion leaves the uploaded document accessible in All materials without inventing a Source. A successful later extraction creates a new immutable source snapshot rather than rewriting an earlier abstract-only source.

### Notes

Include only `file_kind=note`, default `updated_at desc`. Cards show title, up to three lines of plain-text content, last edited date, and note format. Show “Organizational note” as the type. A hypothesis tag is displayed as a tag, not a claim kind.

Fetch the existing bounded note content only for visible cards. Do not show an empty snippet while loading as if the note were blank. The inspector provides full editing, existing revision history, tags, explicit relations, and collection actions. New note requires the existing title and content fields. This version does not introduce auto-titling, autosave, or durable draft recovery.

### Media & data

Include artifact kinds `image`, `video`, and `dataset`, combined with OR. Default `created_at desc`. Show their actual origins as text badges. Derived images and simulated video remain in the view alongside observed inputs, visibly distinguished.

- Image: uncropped thumbnail, name, dimensions when recorded, origin, and added date.
- Video: saved poster if one exists. Otherwise use a video-type placeholder with duration when available. Do not generate a poster service or autoplay a collection of recordings.
- Dataset: name, MIME/format, size, origin, and associated experiment/run when recorded. Do not guess row counts or chart arbitrary columns.

The inspector shows safe media playback or the existing bounded text/CSV preview, parent artifacts, and provenance links. **Open in Experiment Studio** requires an existing recorded experiment association. **Upload file** imports a project material directly, without requiring an experiment. Audio capture and new modalities stay outside the bouncing-ball MVP.

### Findings

Include only `origin_type=claim`, default `created_at desc`. Use statement-first claim cards with recorded kind, citation and measurement references, assumptions, and limitations. This version has no kind-filter query. Card kind labels help scanning without pretending to filter the entire server result by a loaded-page subset.

Evidence expands within a card or opens the inspector. Charts appear only under the relationship rules in the research specification. **Continue research in Chat** opens an editable prompt and sends nothing automatically.

### Measurements

Include only `origin_type=run_measurements`, default `created_at desc`. One card represents a run's set, not a single scalar or an invented project aggregate.

Each card shows experiment, execution date/state, saved measurement count, first chart if available, and three sample rows with units and scientific qualifications. The inspector shows run/experiment links, saved chart/media gallery, ten sample rows, and measurement export. Detailed series selection and full measurements stay in Results.

Grouping is a presentation of the loaded page by experiment ID, with groups ordered by their newest loaded run. Display “Grouping loaded results” and allow the same group to extend when more pages arrive. Do not claim that each group is complete. This avoids requesting an entire project's history on page load.

### All materials

Include all catalog kinds, default `created_at desc`. Offer a compact list with name, type, origin, date, tags, and an independent selection checkbox. Users can change sort to name or recently updated.

Keep code, logs, environment/provenance files, experiment records, and terminal runs accessible here. Trash applies to notes according to existing rules. Bulk tagging and explicit collection membership work here with the current protected-system-tag behavior. Reading code or a log does not execute it.

## 4. Saved views and collections

The unit of persistence is the existing `Collection`, extended with optional presentation metadata. No parallel SavedView resource is created.

**Save view** opens a form with name, description, and presentation. The form describes the supported active name/tag/status constraints and the curated preset's structural filter. Saving creates a dynamic collection. After success, open it by its returned ID. Failure retains the form and the same command identity for an unchanged retry.

The preset contributes an effective constraint: Literature → source, Notes → note, Media & data → the three artifact kinds, Findings → claim, Measurements → measurement set. Desk and All materials have no type constraint. Save these constraints with dynamic filters, so membership remains meaningful independently of presentation. Changing the presentation later does not silently rewrite that filter.

Explicit collections retain explicit membership. Changing presentation narrows visible content but preserves other members. If records are hidden by the selected presentation, show **This presentation shows matching members. Open All materials to see the collection's other items.** Do not invent a hidden-item count.

Collection presentation stores `preset`, `sort`, and `order`. Switching presentation or sorting is initially local URL state. Show **Save presentation** when it differs from the collection's persisted metadata. Saving PATCHes only presentation with `If-Match`. It does not change a dynamic collection's membership filter. Editing that filter remains an explicit collection-edit action.

On a revision conflict keep the unsaved presentation, reload the saved collection, and offer Use saved or Retry my presentation against the new revision. Do not merge fields silently. Deleting a collection removes its organization and saved presentation, never its materials. Confirm deletion with that consequence. An open deleted collection displays its unavailable state and a return-to-Materials action.

## 5. URL and restoration contract

Use `/projects/:project_id/materials` with:

- `view=desk|literature|notes|media-data|findings|measurements|all`.
- Existing `collection`, `q`, `tag`, and `file` parameters.
- `sort=created_at|updated_at|name`, `order=asc|desc`, and `status=active|trashed|all`.

Explicit valid URL parameters override a collection's saved presentation. Missing parameters inherit it, then the preset default. An unknown view falls back to Desk with a small “Unknown view” notice. Unknown filters or unavailable collections show a recoverable error, not a silently different collection.

Existing `source`, `claim`, and `artifact` links remain valid. Resolve to catalog identity within the project, independently of current search filters. Open a linked item even if it is outside the visible view, with “Opened from a link. This item is outside the current view.” Closing preserves the browse state. Never page through an unrelated filtered list indefinitely looking for a linked origin.

Keep list scroll in project-scoped session state keyed by normalized view/collection/filter state. Browser Back closes inspection first and restores the originating card and scroll. Returning after Studio or Results restores the prior loaded pages from the shared cache and the scroll anchor. If the anchor no longer exists, preserve the nearest surviving preceding item. A direct deep link has no required originating card.

## 6. Queries and failure behavior

Use `/files` as the ordered selection source and existing record/artifact detail APIs for visible-card hydration. File kind and origin define type. User-applied tags cannot substitute for artifact-kind filtering. Name search and collection constraints are applied before pagination on the backend.

Use the proposed `features.workspace_views` gate before sending artifact-kind filters or writing presentation metadata. With only `workspace_files`, retain the existing catalog UI and scientific tools. With neither capability, retain the existing artifact fallback. Do not retry an unsupported field by silently dropping the user's intended filter.

Paper controls use the existing `features.full_text_papers` independently. Terminal scratch and session transcripts do not enter Materials automatically. The [terminal contract](terminal-contract.md) has no artifact-publishing operation. Terminal UI integration is separate work. [HPC](hpc-contract.md) remains disabled by the current user decision and adds no new Materials preset or compute-launch widget here.

Cache selection by project, normalized filters, sort, and order. Use shared scientific detail keys and hash/revision-specific content keys. Fetch no off-screen video bytes for a card grid. Load notes/media previews for visible cards only, and cancel obsolete requests on project/view changes. Keep a failed individual card as a named placeholder with Retry.

## 7. Acceptance scenarios

- A researcher reaches literature cards by selecting Literature without typing a name or configuring filters.
- A note tagged reports remains a note. A video tagged charts remains a video. Curated view membership follows authoritative fields.
- A full-text source opens extracted paragraphs and their saved locators, with original and extracted downloads available. Paper artifacts remain accessible in All materials. Terminal scratch is not presented as published material.
- A mixed explicit collection switches between Literature and All materials without losing any member.
- Saving a dynamic view and reopening it in another browser restores membership filters, presentation, and order. A local unsaved presentation does not overwrite the shared one.
- More than 24 matches paginate in the same order and grouping labels remain honest. Changing a filter starts a new cursor sequence.
- Source/artifact deep links open despite an unrelated current search. Closing and Back restore the original context.
- Archived, missing, failed, and unsupported states remain distinguishable. All primary actions work by keyboard at narrow width and 200% zoom.

Implementation amendment: Materials defaults to Desk when no view or saved collection presentation
is selected. Upload file is available on Desk and the other Materials views, without
requiring an experiment. All materials remains the raw project inventory.
