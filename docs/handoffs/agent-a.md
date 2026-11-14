# Agent A handoff — draft complete, awaiting Agent C foundation

> Historical handoff. The foundation-waiting status and tabbed Research layout below describe the original delivery, not the current runtime. For the next work use the public [Research desk](../research-workspace-spec.md), [Materials views](../materials-views-spec.md), and [Reports](../reports-spec.md) specifications. Their cards, dimensions, responsive layout, and interactions supersede the earlier presentation. Pending shell work includes Reports navigation and shared widget/card controls. Current repository instructions govern model selection and delegation. This notice records no new implementation or verification.

Status: all Agent A deliverables are drafted. They compile against the contract-derived interface in §3 below. They are **not connected to live data** because C's `contracts/`, `lib/queries/` and `providers/` do not exist yet. No version-control changes have been made.

## 1. Files

Root-level layout (the scaffold has no `src/`).

### Shared styling and UI (`styles/`, `components/ui/`)
- `styles/tokens.css`: spec tokens plus `--color-accent-contrast`, `--color-focus`, `--control-height`, font/size vars, `--sidebar-width`, `--chat-rail-width`.
- `styles/global.css`: imports tokens; reset, focus ring, reduced motion, `.num`, `.prose`, `.sr-only`.
- `components/ui/index.ts` exports: `Button`, `IconButton`, `Field`, `TextInput`, `TextArea`, `Select`, `Dialog`, `Sheet`, `Tabs`, `StatusBadge`, `EmptyState`, `ErrorNotice`, `Skeleton`, `MarkdownView`, `ArtifactLink`, `TimestampLabel`, helpers `describeError`, `errorCode`, `newCommandKey`, and the icon set (`CloseIcon`, `MenuIcon`, `ChatIcon`, `SendIcon`, `PlusIcon`, `PaperclipIcon`, `ExternalIcon`, `ArrowDownIcon`).
- `components/ui/` depends on nothing from C, so it works today.

### Shell (`components/shell/`)
- `ProjectShell` (public): sidebar nav, header, single `ResearchChat`, responsive placement.
- `ProjectHeader`, `ProjectNavigation`, `ConnectionStatus`, archive/restore dialog.
- `hrefs.ts`: builders for every documented route (encodes opaque IDs). Exported for B and C to reuse.
- `useMediaQuery`, `useStoredFlag` (chat-rail preference in localStorage, the only persisted state).

### Projects (`features/projects/`)
- `ProjectsScreen` (public): Active/Archived tabs, pagination, empty/error states, create dialog → navigates to `/projects/:id/research` on confirmed creation.
- `SignInRequired` (public): for C's SessionGate. Takes `login_url: string | null`; with `null` it shows a configuration message, never a dead button.

### Research (`features/research/`)
- `canvas/ResearchScreen` (public): tabs Research question / Sources / Findings / Experiment plans. URL params `tab`, `source`, `claim`.
  - Question: view + edit (name, question, description) with ETag PATCH; on `412` keeps the draft and shows the saved version with "keep mine" / "use saved".
  - Sources: provider filter, cards with retrieval qualification, details pane (abstract, DOI, link, retrieved document, cited excerpts gathered from persisted claims), manual "Add reference" dialog.
  - Findings: observation / inference / hypothesis (labelled "proposed"), citations, measurement and evidence links, assumptions, limitations. A linked claim loads further pages until found, stays visible under any filter, and is focused.
  - Experiment plans: read-only summary (revision, method, hypothesis, variables table, success criteria, calibration, limitations, protocol) with "Open in Studio".
- `chat/`: `ResearchChat`, `MessageList`, `MessageItem`, `ChatComposer`, `AttachmentPicker`, `CitationLink`. Not exported publicly: only ProjectShell mounts it.

## 2. Requests to Agent C

1. **Root layout**: import `@/styles/global.css` in `app/layout.tsx`; drop or reconcile the scaffold `app/globals.css` (Tailwind, Arial body); replace placeholder metadata. Confirm Tailwind is removed or unused (spec says CSS Modules).
2. **Suspense**: `ResearchScreen` uses `useSearchParams`; render it inside `<Suspense>` in the route.
3. **Route mounting**: `/projects` → `ProjectsScreen`; `/projects/[projectId]/layout` → `ProjectRuntime` + `ProjectShell`; `/research` → `ResearchScreen`. SessionGate renders `SignInRequired` with the configured login URL (or `null`), passing `expired` for `SESSION_EXPIRED`.
4. **Markdown renderer**: pick and pin one (HTML disabled, http/https/mailto links only). `MarkdownView` currently shows escaped source text; swap its body, keep `{ markdown, className }` props.
5. **Icons**: A shipped a small inline-SVG set instead of a dependency. If you prefer a library, say so and A will swap the internals.
6. **Interface match**: implement §3 as written, or tell A what differs and A will adapt.

## 3. Interface A compiled against (assumed from spec §5 and the contract)

Types are the contract's wire shapes, verbatim, from `@/contracts/api` (`ID`, `Project`, `Workspace`, `Message`, `Source`, `Citation`, `Claim`, `EvidenceRef`, `Experiment`, `Variable`, `Artifact`, `Run`, `Capabilities`).

```ts
// @/lib/queries
type DetailQuery<T> = { data: T | undefined, etag: string | null, is_loading: boolean, error: unknown, refetch: () => void }
type ListQuery<T> = { items: T[], is_loading: boolean, error: unknown, has_next_page: boolean,
                      is_fetching_next_page: boolean, load_next_page: () => void, refetch: () => void }
// Mutations: TanStack's result as-is.
type Mutation<V, R> = { mutateAsync: (v: V) => Promise<ApiResult<R>>, isPending: boolean, error: unknown, reset: () => void }

useProject(project_id): DetailQuery<Project>
useWorkspace(project_id): DetailQuery<Workspace>
useCapabilities(): DetailQuery<Capabilities>
useProjects({ status }): ListQuery<Project>
useMessages(project_id): ListQuery<Message>           // oldest-first
useSources(project_id, { provider? }): ListQuery<Source>
useClaims(project_id, { run_id? }): ListQuery<Claim>
useExperiments(project_id): ListQuery<Experiment>
useArtifacts(project_id, { kind?, experiment_id?, run_id? }): ListQuery<Artifact>

useCreateProject():          Mutation<{ body: CreateProjectRequest, idempotency_key: string }, Project>
useEditProject(project_id):  Mutation<{ body: EditProjectRequest, etag: string }, Project>
useSubmitMessage(project_id): Mutation<{ body: SubmitMessageRequest, idempotency_key: string },
                                       { user_message: Message, assistant_message: Message, run: Run }>
useCreateSource(project_id): Mutation<{ body: CreateSourceRequest, idempotency_key: string }, Source>

// @/providers
useProjectRuntime(): { project_id: ID, connection: "connecting" | "open" | "reconnecting" | "failed", reconnect: () => void }
```

Errors: A reads `error.code`, `error.message`, `error.request_id` defensively (`describeError`), and branches only on codes: `REVISION_CONFLICT`, `PROJECT_ARCHIVED`, `COMMAND_IN_PROGRESS`, `IDEMPOTENCY_CONFLICT`.

Idempotency: one key per user action; a retry of the same body reuses it; a changed body or `IDEMPOTENCY_CONFLICT` starts a new key. Composer text is cleared only after the `202`.

## 4. Source-review notes

- No fetch/EventSource calls in A code; all data via C hooks. No fabricated records, fixtures or mock data.
- Unresolved claim/source/attachment IDs render "Unavailable reference" / generic labels, never invented metadata.
- External links: only http(s) URLs become anchors (`safeHref`), opened with `rel="noopener noreferrer"`.
- Archived projects disable chat, question edit and add-reference, with an explanation.
- Chat: follows new content only when the reader is near the end; otherwise a "New activity" button. Status changes (not tokens) are announced via a polite live region; first load is not announced.
- Responsive: ≥1280 three columns with collapsible rail; 768–1279 chat in a side sheet (kept mounted so drafts survive closing); <768 menu sheet + full-width chat sheet.

## 5. Known limitations

- Resizing across 1280px moves chat between rail and sheet, remounting it and losing an unsent draft.
- The first assistant message in a project with no prior assistant messages is not announced.
- Measurement links go to the run page (no per-measurement route exists, by design).
- Source details only find cited excerpts in loaded claim pages.
- `tsc` for the whole project fails until C publishes `@/contracts/*`, `@/lib/*`, `@/providers` (intended: missing interfaces fail visibly). A verified its code with a local type stub of §3 outside the repo; `eslint` passes on `components/` and `features/`.

## 6. Unverified (needs human review)

Nothing has been rendered with real data. Visual layout, contrast, keyboard flow, focus restoration, screen-reader announcements, and mobile behavior have not been checked. Primitives can be viewed on the local-only `/dev/ui` gallery (git-excluded; delete before integration).
