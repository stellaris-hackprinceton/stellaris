"use client";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { ID } from "@/contracts/api";
import type { WorkspaceFile } from "@/contracts/catalog";
import { Button, EmptyState, ErrorNotice, Field, ResizeHandle, Select, Sheet, Skeleton, usePanelSize } from "@/components/ui";
import { useCollections, useFiles, useRelations, useTags } from "@/lib/catalog";
import { useCapabilities } from "@/lib/queries";
import { MaterialInspector } from "@/features/materials/MaterialInspector";
import styles from "./graph.module.css";
import { fitToViewport, forceLayout } from "./layout";

const PAGE_SIZE = 100;
const NODE_CAP = 200;
const EDGE_CAP = 200;
const MIN_ZOOM = .4, MAX_ZOOM = 3;
type Point = { x: number; y: number };
type View = { k: number; x: number; y: number };
/** One drawn line per connected pair; direction is kept per relation. */
type Pair = { a: ID; b: ID; forward: boolean; backward: boolean; user: boolean; titles: string[] };

function cluster(file: WorkspaceFile) { return file.file_kind === "record" ? file.origin?.type ?? "record" : file.file_kind; }
const nodeRadius = (degree: number) => degree === 0 ? 4 : Math.min(13, 4.5 + 2.1 * Math.sqrt(degree));

const ROLE_LABEL: Record<string, string> = { artifact: "Artifact", source: "Source", claim: "Finding", experiment: "Experiment", run: "Run", run_measurements: "Measurements", note: "Note", record: "Record" };

export function KnowledgeGraph({ project_id }: { project_id: ID }) {
  const search = useSearchParams();
  const router = useRouter();
  const selectedId = search.get("file");
  const [tag, setTag] = useState("");
  const [collection, setCollection] = useState("");
  const [hoveredId, setHoveredId] = useState<ID | null>(null);
  const [focus, setFocus] = useState<ID | null>(null);
  const [dismissedInspector, setDismissedInspector] = useState<ID | null>(null);
  const [view, setView] = useState<View>({ k: 1, x: 0, y: 0 });
  const [drag, setDrag] = useState<{ id: number; x: number; y: number; origin: Point } | null>(null);
  const [viewport, setViewport] = useState({ width: 900, height: 520 });
  const [graphHeight, setGraphHeight, resetGraphHeight] = usePanelSize("stellaris.graphHeight", 560, 320, 1200);
  const graphRef = useRef<SVGSVGElement>(null);
  const graphWrapRef = useRef<HTMLDivElement>(null);
  const filters = useMemo(() => ({ limit: PAGE_SIZE, ...(tag ? { tags: [tag] } : {}), ...(collection ? { collection_id: collection } : {}) }), [tag, collection]);
  const files = useFiles(project_id, filters);
  const relations = useRelations(project_id, { limit: PAGE_SIZE });
  const tags = useTags(project_id), collections = useCollections(project_id);
  const capabilities = useCapabilities();
  const visible = files.items.slice(0, NODE_CAP);
  const visibleIds = useMemo(() => new Set(visible.map((f) => f.id)), [visible]);
  const matchingEdges = useMemo(() => relations.items.filter((r) => visibleIds.has(r.from_file_id) && visibleIds.has(r.to_file_id)), [relations.items, visibleIds]);
  const edges = matchingEdges.slice(0, EDGE_CAP);
  const names = useMemo(() => new Map(visible.map((f) => [f.id, f.name])), [visible]);
  // Collapse parallel and reverse relations into one line per pair so hubs are not buried in arrowheads.
  const pairs = useMemo(() => {
    const byPair = new Map<string, Pair>();
    for (const edge of edges) {
      if (edge.from_file_id === edge.to_file_id) continue;
      const [a, b] = edge.from_file_id < edge.to_file_id ? [edge.from_file_id, edge.to_file_id] : [edge.to_file_id, edge.from_file_id];
      const key = `${a}\u0000${b}`;
      const pair = byPair.get(key) ?? { a, b, forward: false, backward: false, user: false, titles: [] };
      if (edge.from_file_id === a) pair.forward = true; else pair.backward = true;
      if (edge.created_by === "user") pair.user = true;
      pair.titles.push(`${edge.type}: ${names.get(edge.from_file_id) ?? edge.from_file_id} → ${names.get(edge.to_file_id) ?? edge.to_file_id}`);
      byPair.set(key, pair);
    }
    return [...byPair.values()];
  }, [edges, names]);
  const adjacency = useMemo(() => {
    const map = new Map<ID, Set<ID>>(visible.map((f) => [f.id, new Set<ID>()]));
    for (const p of pairs) { map.get(p.a)?.add(p.b); map.get(p.b)?.add(p.a); }
    return map;
  }, [visible, pairs]);
  const radiusOf = useCallback((id: ID) => nodeRadius(adjacency.get(id)?.size ?? 0), [adjacency]);
  // Layout depends only on files and links; resizing refits without re-running the simulation.
  const layoutPoints = useMemo(() => forceLayout(visible.map((f) => f.id), pairs.map((p) => ({ source: p.a, target: p.b })), radiusOf), [visible, pairs, radiusOf]);
  const positions = useMemo(() => fitToViewport(layoutPoints, viewport.width, viewport.height, 48), [layoutPoints, viewport]);
  const selected = visible.find((f) => f.id === selectedId);
  const activeId = hoveredId ?? focus ?? (selected ? selected.id : null);
  useEffect(() => {
    if (selectedId && !selected && files.has_next_page && files.items.length < NODE_CAP && !files.is_fetching_next_page) void files.load_next_page();
  }, [selectedId, selected, files]);
  // Hovering, focusing or selecting a file highlights it with its direct links; everything else recedes.
  const highlighted = useMemo(() => activeId ? new Set<ID>([activeId, ...(adjacency.get(activeId) ?? [])]) : null, [activeId, adjacency]);
  const labelled = useMemo(() => {
    if (highlighted) return new Set([...highlighted].sort((x, y) => (x === activeId ? -1 : y === activeId ? 1 : (adjacency.get(y)?.size ?? 0) - (adjacency.get(x)?.size ?? 0))).slice(0, 14));
    if (view.k >= 1.6) return new Set(visible.map((f) => f.id));
    // At rest, name only the most connected files so the picture stays readable.
    return new Set(visible.filter((f) => (adjacency.get(f.id)?.size ?? 0) >= 2).sort((x, y) => (adjacency.get(y.id)?.size ?? 0) - (adjacency.get(x.id)?.size ?? 0)).slice(0, 6).map((f) => f.id));
  }, [highlighted, activeId, adjacency, view.k, visible]);
  const setSelected = useCallback((id: ID | null) => {
    setDismissedInspector(null);
    setFocus(null);
    const params = new URLSearchParams(search.toString());
    if (id) params.set("file", id); else params.delete("file");
    router.replace(`${location.pathname}${params.size ? `?${params}` : ""}`, { scroll: false });
  }, [router, search]);
  const loadMoreNodes = () => { if (visible.length < NODE_CAP && files.has_next_page) void files.load_next_page(); };
  const loadMoreEdges = () => { if (relations.has_next_page) void relations.load_next_page(); };
  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => { if (e.target !== e.currentTarget && !(e.target as Element).hasAttribute("data-backdrop")) return; e.currentTarget.setPointerCapture(e.pointerId); setDrag({ id: e.pointerId, x: e.clientX, y: e.clientY, origin: { x: view.x, y: view.y } }); };
  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => { if (drag?.id === e.pointerId) { const rect = e.currentTarget.getBoundingClientRect(); const ratio = viewport.width / rect.width; setView((v) => ({ ...v, x: drag.origin.x + (e.clientX - drag.x) * ratio, y: drag.origin.y + (e.clientY - drag.y) * ratio })); } };
  /** Zooms by `factor` keeping the point (cx, cy), in viewBox units, fixed on screen. */
  const zoomAt = useCallback((factor: number, cx: number, cy: number) => setView((v) => {
    const k = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, v.k * factor)), ratio = k / v.k;
    return { k, x: cx - (cx - v.x) * ratio, y: cy - (cy - v.y) * ratio };
  }), []);
  useEffect(() => {
    const element = graphRef.current;
    const container = graphWrapRef.current;
    if (!element || !container || files.is_loading || capabilities.is_loading || !capabilities.data?.features.workspace_files) return;
    const resize = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) setViewport({ width: Math.round(rect.width), height: Math.round(rect.height) });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    const zoomAtWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = element.getBoundingClientRect(), ratio = rect.width ? element.viewBox.baseVal.width / rect.width : 1;
      zoomAt(event.deltaY < 0 ? 1.12 : 1 / 1.12, (event.clientX - rect.left) * ratio, (event.clientY - rect.top) * ratio);
    };
    element.addEventListener("wheel", zoomAtWheel, { passive: false });
    return () => { observer.disconnect(); element.removeEventListener("wheel", zoomAtWheel); };
  }, [files.is_loading, capabilities.is_loading, capabilities.data?.features.workspace_files, zoomAt]);

  if (!capabilities.is_loading && !capabilities.data?.features.workspace_files) return <div className={styles.screen} data-workspace-wide="true">
    <header className={styles.header}><div><h1>Connections</h1><p>Explore saved files and their recorded links. Lines reflect explicit relations or provenance recorded by Stellaris.</p></div></header>
    <EmptyState title="Project materials are unavailable here">This server does not currently provide the project file catalog. Open Overview for saved questions and findings, or try again after catalog support is enabled.</EmptyState>
  </div>;

  return <div className={styles.screen} data-workspace-wide="true">
    <header className={styles.header}><div><h1>Connections</h1><p>Explore saved files and their recorded links. Lines reflect explicit relations or provenance recorded by Stellaris.</p></div>
      <div className={styles.controls}>
        <Field label="Tag"><Select value={tag} onChange={(e) => { setTag(e.target.value); setFocus(null); }}><option value="">All tags</option>{tags.items.map((t) => <option key={t.slug} value={t.slug}>{t.label}</option>)}</Select></Field>
        <Field label="Collection"><Select value={collection} onChange={(e) => { setCollection(e.target.value); setFocus(null); }}><option value="">All files</option>{collections.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
      </div>
    </header>
        {files.error && <ErrorNotice title={files.items.length ? "Some project files could not be loaded" : "Project files could not be loaded"} message={files.items.length ? "The graph includes files received so far." : "Try again after checking the project connection."} action={<Button onClick={files.refetch}>Try again</Button>} />}
    {files.is_loading ? <Skeleton height="24rem" /> : files.items.length === 0 ? <EmptyState title="No files match this view">Add or restore project materials in Library. The graph includes only catalog files and recorded relations.</EmptyState> : <>
      <div className={styles.toolbar}>
        <p aria-live="polite">{visible.length} files loaded{files.has_next_page ? " so far" : " (all matching files)"} · {edges.length} links between these files{relations.has_next_page ? " in the loaded relation pages" : " across the loaded relation catalog"}</p>
        <div className={styles.buttons}><Button onClick={() => zoomAt(1.25, viewport.width / 2, viewport.height / 2)}>Zoom in</Button><Button onClick={() => zoomAt(1 / 1.25, viewport.width / 2, viewport.height / 2)}>Zoom out</Button><Button onClick={() => { setView({ k: 1, x: 0, y: 0 }); setFocus(null); }}>Reset view</Button></div>
      </div>
      <div ref={graphWrapRef} className={styles.graphWrap} style={{ "--graph-height": `${graphHeight}px` } as CSSProperties}>
        <ResizeHandle label="Resize graph height" axis="y" value={graphHeight} min={320} max={1200} onChange={setGraphHeight} onReset={resetGraphHeight} className={styles.heightHandle} />
        <svg ref={graphRef} className={styles.graph} viewBox={`0 0 ${viewport.width} ${viewport.height}`} role="group" aria-label="Interactive project knowledge graph" data-highlighting={highlighted ? "true" : undefined} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={() => setDrag(null)} onPointerCancel={() => setDrag(null)}>
          <defs>
            <marker id="graph-arrow" viewBox="0 0 8 8" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" refX="8" refY="4" orient="auto-start-reverse"><path d="M0,0.5 L8,4 L0,7.5 z" className={styles.arrow} /></marker>
            <marker id="graph-arrow-user" viewBox="0 0 8 8" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" refX="8" refY="4" orient="auto-start-reverse"><path d="M0,0.5 L8,4 L0,7.5 z" className={styles.arrowUser} /></marker>
          </defs>
          <rect data-backdrop="true" width={viewport.width} height={viewport.height} fill="transparent" />
          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            <g className={styles.edges}>{pairs.map((pair) => {
              const a = positions.get(pair.a), b = positions.get(pair.b); if (!a || !b) return null;
              const on = !!highlighted && highlighted.has(pair.a) && highlighted.has(pair.b) && (pair.a === activeId || pair.b === activeId);
              const length = Math.hypot(b.x - a.x, b.y - a.y) || 1, ux = (b.x - a.x) / length, uy = (b.y - a.y) / length;
              // Trim to the node edges so arrowheads touch, rather than sit inside, their files.
              const ta = radiusOf(pair.a) + 2, tb = radiusOf(pair.b) + 2;
              if (length <= ta + tb) return null;
              const marker = `url(#${pair.user ? "graph-arrow-user" : "graph-arrow"})`;
              return <g key={`${pair.a}-${pair.b}`} className={styles.edge} data-origin={pair.user ? "user" : "system"} data-active={on || undefined} data-dim={highlighted && !on ? "true" : undefined}>
                <title>{pair.titles.join("\n")}</title>
                <line x1={a.x + ux * ta} y1={a.y + uy * ta} x2={b.x - ux * tb} y2={b.y - uy * tb} markerEnd={on && pair.forward ? marker : undefined} markerStart={on && pair.backward ? marker : undefined} />
                <line className={styles.edgeHit} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
              </g>;
            })}</g>
            <g>{visible.map((file) => {
              const p = positions.get(file.id); if (!p) return null;
              const role = cluster(file), degree = adjacency.get(file.id)?.size ?? 0, r = nodeRadius(degree);
              return <g key={file.id} className={styles.node} transform={`translate(${p.x} ${p.y})`} data-role={role} data-active={activeId === file.id || undefined} data-dim={highlighted && !highlighted.has(file.id) ? "true" : undefined} role="button" tabIndex={0} aria-label={`${file.name}, ${ROLE_LABEL[role] ?? role}, ${degree} linked ${degree === 1 ? "file" : "files"}`} aria-pressed={selectedId === file.id} onPointerEnter={() => setHoveredId(file.id)} onPointerLeave={() => setHoveredId(null)} onFocus={() => setHoveredId(file.id)} onBlur={() => setHoveredId(null)} onClick={() => setSelected(file.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(file.id); } if (e.key.toLowerCase() === "f") setFocus(file.id); }}>
                <title>{file.name}</title>
                <circle className={styles.hitTarget} r={Math.max(r + 6, 12)} />
                {selectedId === file.id && <circle className={styles.selectedRing} r={r + 4} />}
                <circle className={styles.visibleNode} r={r} />
              </g>;
            })}</g>
            {/* Labels draw last so a hovered name is never hidden behind other files or links. */}
            <g className={styles.labels} aria-hidden="true">{visible.filter((f) => labelled.has(f.id)).map((file) => {
              const p = positions.get(file.id); if (!p) return null;
              const r = radiusOf(file.id), screenX = p.x * view.k + view.x, flip = screenX > viewport.width * .72;
              const name = file.name.length > 40 ? `${file.name.slice(0, 38)}…` : file.name;
              return <text key={file.id} data-active={activeId === file.id || undefined} x={p.x + (flip ? -(r + 6) : r + 6)} y={p.y + 4} textAnchor={flip ? "end" : "start"} style={{ fontSize: `${13 / Math.max(view.k, .8)}px` }}>{name}</text>;
            })}</g>
          </g>
        </svg>
      </div>
      <p className={styles.hint}>Hover a file to see its links and their direction. Drag to pan, scroll to zoom, select a file to inspect it. Press F on a file to keep its neighborhood in focus.</p>
      <div className={styles.legend} aria-label="Graph legend">
        <div className={styles.roleLegend}>{[...new Set(visible.map(cluster))].sort().map((role) => <span key={role}><i data-role={role} />{ROLE_LABEL[role] ?? role}</span>)}<span className={styles.sizeKey}>Larger dots have more links</span></div>
        <div className={styles.lineLegend}><span><i data-origin="system" />Recorded provenance</span><span><i data-origin="user" />User relation</span></div>
      </div>
      <div className={styles.loaders}>
        {files.has_next_page && visible.length < NODE_CAP && <Button onClick={loadMoreNodes} pending={files.is_fetching_next_page}>Load more files</Button>}
        {files.has_next_page && visible.length >= NODE_CAP && <p>Graph rendering is capped at {NODE_CAP} files. Narrow by tag or collection to explore the remaining catalog.</p>}
        {relations.has_next_page && <Button onClick={loadMoreEdges} pending={relations.is_fetching_next_page}>Load more relation pages</Button>}
        {matchingEdges.length > EDGE_CAP && <p>Showing {EDGE_CAP} matching links; the graph limits rendered links for clarity. Filter to a smaller file set.</p>}
        {relations.error && <ErrorNotice title="Some relations could not be loaded" message="The graph shows only relations received from the catalog." action={<Button onClick={relations.refetch}>Retry relations</Button>} />}
        {!relations.is_loading && !relations.error && !relations.has_next_page && relations.items.length === 0 && <p>No relations are recorded in this project.</p>}
        {!relations.is_loading && !relations.error && !relations.has_next_page && relations.items.length > 0 && edges.length === 0 && <p>No recorded relations connect the files currently shown.</p>}
        {relations.has_next_page && edges.length === 0 && <p>No links between these files are in the loaded pages yet. Load more relation pages before drawing a conclusion.</p>}
        {selectedId && !selected && !files.is_loading && (!files.has_next_page || files.items.length >= NODE_CAP) && <p role="status">This file is not in the current graph filter or first {NODE_CAP} loaded files. Clear filters or use Library to locate it.</p>}
      </div>
      {(tags.error || collections.error) && <div className={styles.loaders}>
        {tags.error && <ErrorNotice title="Tags could not be loaded" message="Retry or continue browsing files without tag choices." action={<Button onClick={tags.refetch}>Retry tags</Button>} />}
        {collections.error && <ErrorNotice title="Collections could not be loaded" message="Retry or continue browsing files without collection choices." action={<Button onClick={collections.refetch}>Retry collections</Button>} />}
      </div>}
      {(tags.has_next_page || collections.has_next_page) && <div className={styles.loaders}>
        {tags.has_next_page && <Button onClick={() => void tags.load_next_page()} pending={tags.is_fetching_next_page}>Load more tag choices</Button>}
        {collections.has_next_page && <Button onClick={() => void collections.load_next_page()} pending={collections.is_fetching_next_page}>Load more collection choices</Button>}
      </div>}
      {selected && <div className={styles.focusControls}><span>Selected: {selected.name}</span><Button onClick={() => setDismissedInspector(null)}>Inspect material</Button><Button onClick={() => setFocus(selected.id)} aria-pressed={focus === selected.id}>Focus neighborhood</Button><Button onClick={() => setFocus(null)} disabled={!focus}>Show all nodes</Button></div>}
      <details className={styles.fileList}><summary>Library files in this view <span>{visible.length} files</span></summary>
        <ul>{visible.map((f) => <li key={f.id}><button type="button" aria-pressed={selectedId === f.id} onClick={() => setSelected(f.id)}><strong>{f.name}</strong><span>{ROLE_LABEL[cluster(f)] ?? cluster(f)} · {f.scientific_origin ?? "origin not recorded"}</span></button></li>)}</ul>
      </details>
    </>}
    <Sheet open={!!selected && dismissedInspector !== selected.id} onClose={() => setDismissedInspector(selected!.id)} title="Material details">
      {selected && <MaterialInspector project_id={project_id} file_id={selected.id} />}
    </Sheet>
  </div>;
}
