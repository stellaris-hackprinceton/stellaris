"use client";
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { ID } from "@/contracts/api";
import type { WorkspaceFile } from "@/contracts/catalog";
import { Button, EmptyState, ErrorNotice, Field, Select, Sheet, Skeleton } from "@/components/ui";
import { useCollections, useFiles, useRelations, useTags } from "@/lib/catalog";
import { useCapabilities } from "@/lib/queries";
import { MaterialInspector } from "@/features/materials/MaterialInspector";
import styles from "./graph.module.css";

const PAGE_SIZE = 100;
const NODE_CAP = 200;
const EDGE_CAP = 200;
type Point = { x: number; y: number };

function cluster(file: WorkspaceFile) { return file.file_kind === "record" ? file.origin?.type ?? "record" : file.file_kind; }
function layout(files: WorkspaceFile[], width: number, height: number) {
  const ordered = [...files].sort((a, b) => cluster(a).localeCompare(cluster(b)) || a.id.localeCompare(b.id));
  const points = new Map<ID, Point>();
  const cx = width / 2, cy = height / 2, rx = Math.max(30, cx - 56), ry = Math.max(30, cy - 56);
  const anchor = ordered.find(file => file.origin?.type === "run") ?? ordered.find(file => file.origin?.type === "claim") ?? ordered[0];
  if (!anchor) return { points, height };
  if (ordered.length <= 12) {
    points.set(anchor.id, { x: cx, y: cy });
    const rest = ordered.filter(file => file.id !== anchor.id);
    rest.forEach((file, index) => {
      const angle = -Math.PI / 2 + index * Math.PI * 2 / rest.length;
      points.set(file.id, { x: cx + Math.cos(angle) * rx, y: cy + Math.sin(angle) * ry });
    });
  } else {
    ordered.forEach((file, index) => {
      const angle = index * 2.399963, radius = Math.sqrt((index + .5) / ordered.length);
      points.set(file.id, { x: cx + Math.cos(angle) * rx * radius, y: cy + Math.sin(angle) * ry * radius });
    });
    const minimum = Math.min(52, Math.sqrt(width * height / ordered.length) * .8);
    const rows = [...points.values()];
    for (let pass = 0; pass < 24; pass++) for (let i = 0; i < rows.length; i++) for (let j = i + 1; j < rows.length; j++) {
      const a = rows[i], b = rows[j], dx = b.x - a.x, dy = b.y - a.y, distance = Math.hypot(dx, dy) || 1;
      if (distance >= minimum) continue;
      const shift = (minimum - distance) / 2, x = dx / distance * shift, y = dy / distance * shift;
      a.x = Math.max(28, Math.min(width - 28, a.x - x)); a.y = Math.max(28, Math.min(height - 28, a.y - y));
      b.x = Math.max(28, Math.min(width - 28, b.x + x)); b.y = Math.max(28, Math.min(height - 28, b.y + y));
    }
  }
  return { points, height };
}

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
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 });
  const [drag, setDrag] = useState<{ id: number; x: number; y: number; origin: Point } | null>(null);
  const [viewport, setViewport] = useState({ width: 900, height: 430 });
  const graphRef = useRef<SVGSVGElement>(null);
  const graphWrapRef = useRef<HTMLDivElement>(null);
  const filters = useMemo(() => ({ limit: PAGE_SIZE, ...(tag ? { tags: [tag] } : {}), ...(collection ? { collection_id: collection } : {}) }), [tag, collection]);
  const files = useFiles(project_id, filters);
  const relations = useRelations(project_id, { limit: PAGE_SIZE });
  const tags = useTags(project_id), collections = useCollections(project_id);
  const capabilities = useCapabilities();
  const visible = files.items.slice(0, NODE_CAP);
  const visibleIds = useMemo(() => new Set(visible.map((f) => f.id)), [visible]);
  const geometry = useMemo(() => layout(visible, viewport.width, viewport.height), [visible, viewport]);
  const positions = geometry.points;
  const matchingEdges = useMemo(() => relations.items.filter((r) => visibleIds.has(r.from_file_id) && visibleIds.has(r.to_file_id)), [relations.items, visibleIds]);
  const edges = matchingEdges.slice(0, EDGE_CAP);
  const selected = visible.find((f) => f.id === selectedId);
  const activeCaptionId = hoveredId ?? focus ?? selectedId;
  const activeEdgeId = activeCaptionId ? edges.find((edge) => edge.from_file_id === activeCaptionId || edge.to_file_id === activeCaptionId)?.id : undefined;
  useEffect(() => {
    if (selectedId && !selected && files.has_next_page && files.items.length < NODE_CAP && !files.is_fetching_next_page) void files.load_next_page();
  }, [selectedId, selected, files]);
  const neighbors = useMemo(() => {
    if (!focus) return null;
    const ids = new Set<ID>([focus]);
    for (const edge of edges) if (edge.from_file_id === focus || edge.to_file_id === focus) { ids.add(edge.from_file_id); ids.add(edge.to_file_id); }
    return ids;
  }, [focus, edges]);
  const setSelected = useCallback((id: ID | null) => {
    setDismissedInspector(null);
    setFocus(null);
    const params = new URLSearchParams(search.toString());
    if (id) params.set("file", id); else params.delete("file");
    router.replace(`${location.pathname}${params.size ? `?${params}` : ""}`, { scroll: false });
  }, [router, search]);
  const loadMoreNodes = () => { if (visible.length < NODE_CAP && files.has_next_page) void files.load_next_page(); };
  const loadMoreEdges = () => { if (relations.has_next_page) void relations.load_next_page(); };
  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => { if (e.target !== e.currentTarget) return; e.currentTarget.setPointerCapture(e.pointerId); setDrag({ id: e.pointerId, x: e.clientX, y: e.clientY, origin: pan }); };
  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => { if (drag?.id === e.pointerId) { const rect = e.currentTarget.getBoundingClientRect(); setPan({ x: drag.origin.x + (e.clientX - drag.x) * viewport.width / rect.width, y: drag.origin.y + (e.clientY - drag.y) * geometry.height / rect.height }); } };
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
    const zoomAtWheel = (event: WheelEvent) => { event.preventDefault(); setZoom((v) => Math.max(.55, Math.min(2.2, v * (event.deltaY < 0 ? 1.1 : .9)))); };
    element.addEventListener("wheel", zoomAtWheel, { passive: false });
    return () => { observer.disconnect(); element.removeEventListener("wheel", zoomAtWheel); };
  }, [files.is_loading, capabilities.is_loading, capabilities.data?.features.workspace_files]);

  if (!capabilities.is_loading && !capabilities.data?.features.workspace_files) return <div className={styles.screen}>
    <header className={styles.header}><div><h1>Knowledge graph</h1><p>Explore saved files and their recorded links. Lines reflect explicit relations or provenance recorded by Stellaris.</p></div></header>
    <EmptyState title="Project materials are unavailable here">This server does not currently provide the project file catalog. Open Research for saved questions and findings, or try again after catalog support is enabled.</EmptyState>
  </div>;

  return <div className={styles.screen}>
    <header className={styles.header}><div><h1>Knowledge graph</h1><p>Explore saved files and their recorded links. Lines reflect explicit relations or provenance recorded by Stellaris.</p></div>
      <div className={styles.controls}>
        <Field label="Tag"><Select value={tag} onChange={(e) => { setTag(e.target.value); setFocus(null); }}><option value="">All tags</option>{tags.items.map((t) => <option key={t.slug} value={t.slug}>{t.label}</option>)}</Select></Field>
        <Field label="Collection"><Select value={collection} onChange={(e) => { setCollection(e.target.value); setFocus(null); }}><option value="">All files</option>{collections.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
      </div>
    </header>
        {files.error && <ErrorNotice title={files.items.length ? "Some project files could not be loaded" : "Project files could not be loaded"} message={files.items.length ? "The graph includes files received so far." : "Try again after checking the project connection."} action={<Button onClick={files.refetch}>Try again</Button>} />}
    {files.is_loading ? <Skeleton height="24rem" /> : files.items.length === 0 ? <EmptyState title="No files match this view">Add or restore project materials in Materials. The graph includes only catalog files and recorded relations.</EmptyState> : <>
      <div className={styles.toolbar}>
        <p aria-live="polite">{visible.length} files loaded{files.has_next_page ? " so far" : " (all matching files)"} · {edges.length} links between these files{relations.has_next_page ? " in the loaded relation pages" : " across the loaded relation catalog"}</p>
        <div className={styles.buttons}><Button onClick={() => { setZoom((v) => Math.min(2.2, v * 1.2)); }}>Zoom in</Button><Button onClick={() => { setZoom((v) => Math.max(.55, v / 1.2)); }}>Zoom out</Button><Button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); setFocus(null); }}>Reset view</Button></div>
      </div>
      <div ref={graphWrapRef} className={styles.graphWrap}>
        <svg ref={graphRef} className={styles.graph} viewBox={`0 0 ${viewport.width} ${geometry.height}`} preserveAspectRatio="none" role="group" aria-label="Interactive project knowledge graph" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={() => setDrag(null)} onPointerCancel={() => setDrag(null)}>
          <g transform={`translate(${pan.x} ${pan.y}) translate(${viewport.width / 2} ${geometry.height / 2}) scale(${zoom}) translate(${-viewport.width / 2} ${-geometry.height / 2})`}>
            {edges.map((edge) => { const a = positions.get(edge.from_file_id), b = positions.get(edge.to_file_id); if (!a || !b) return null; const length = Math.hypot(b.x-a.x,b.y-a.y) || 1, margin = Math.min(18,length*.3), dx = (b.x-a.x)/length*margin, dy = (b.y-a.y)/length*margin; return <g key={edge.id} className={styles.edge} data-origin={edge.created_by} opacity={neighbors && (!neighbors.has(edge.from_file_id) || !neighbors.has(edge.to_file_id)) ? .12 : .8}><title>{`${edge.type}: ${visible.find(file=>file.id===edge.from_file_id)?.name ?? edge.from_file_id} to ${visible.find(file=>file.id===edge.to_file_id)?.name ?? edge.to_file_id}`}</title><line x1={a.x+dx} y1={a.y+dy} x2={b.x-dx} y2={b.y-dy} markerEnd="url(#arrow)" />{edge.id === activeEdgeId && <text x={(a.x+b.x)/2} y={(a.y+b.y)/2-5}>{edge.type}</text>}</g>; })}
            <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="var(--color-control-border)" /></marker></defs>
            {visible.map((file) => { const p = positions.get(file.id)!; const dim = neighbors && !neighbors.has(file.id); const role = cluster(file); return <g key={file.id} className={styles.node} transform={`translate(${p.x} ${p.y})`} data-role={role} data-active={activeCaptionId === file.id || undefined} role="button" tabIndex={0} aria-label={`${file.name}, ${ROLE_LABEL[role] ?? role}, ${edges.filter((e) => e.from_file_id === file.id || e.to_file_id === file.id).length} loaded links`} aria-pressed={selectedId === file.id} opacity={dim ? .22 : 1} onPointerEnter={() => setHoveredId(file.id)} onPointerLeave={() => setHoveredId(null)} onFocus={() => setHoveredId(file.id)} onBlur={() => setHoveredId(null)} onClick={() => setSelected(file.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(file.id); } if (e.key.toLowerCase() === "f") setFocus(file.id); }}>
              <title>{file.name}</title><circle className={styles.hitTarget} r="24" /><circle className={styles.visibleNode} r={file.file_kind === "record" ? 12 : 15} data-kind={file.file_kind} /><text y="31" x={p.x < viewport.width / 3 ? 18 : p.x > viewport.width * 2 / 3 ? -18 : 0} style={{ textAnchor: p.x < viewport.width / 3 ? "start" : p.x > viewport.width * 2 / 3 ? "end" : "middle" }}>{file.name.length > 34 ? `${file.name.slice(0, 32)}…` : file.name}</text>
            </g>; })}
          </g>
        </svg>
      </div>
      <p className={styles.hint}>Drag to pan · scroll to zoom · select a node to inspect. Press F on a node to focus its loaded neighborhood.</p>
      <div className={styles.legend} aria-label="Graph legend">
        <div className={styles.roleLegend}>{[...new Set(visible.map(cluster))].map((role) => <span key={role}><i data-role={role} />{ROLE_LABEL[role] ?? role}</span>)}</div>
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
        {selectedId && !selected && !files.is_loading && (!files.has_next_page || files.items.length >= NODE_CAP) && <p role="status">This file is not in the current graph filter or first {NODE_CAP} loaded files. Clear filters or use Materials to locate it.</p>}
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
      <details className={styles.fileList}><summary>Materials in this view <span>{visible.length} files</span></summary>
        <ul>{visible.map((f) => <li key={f.id}><button type="button" aria-pressed={selectedId === f.id} onClick={() => setSelected(f.id)}><strong>{f.name}</strong><span>{ROLE_LABEL[cluster(f)] ?? cluster(f)} · {f.scientific_origin ?? "origin not recorded"}</span></button></li>)}</ul>
      </details>
    </>}
    <Sheet open={!!selected && dismissedInspector !== selected.id} onClose={() => setDismissedInspector(selected!.id)} title="Material details">
      {selected && <MaterialInspector project_id={project_id} file_id={selected.id} />}
    </Sheet>
  </div>;
}
