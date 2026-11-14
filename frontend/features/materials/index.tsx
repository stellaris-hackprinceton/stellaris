'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import type { WorkspaceFile } from '@/contracts/catalog'
import { catalogApi, useCatalog, useCatalogFeatures, useCatalogMutation, useCollections, useFiles, useOriginFile, useTags } from '@/lib/catalog'
import { MaterialsViews, type MaterialsIntegrations } from './MaterialsViews'
import { CHAT_PROMPT_EVENT, LiteratureActions } from '@/features/research/desk/LiteratureWidget'
import { SourceInspector } from '@/features/research/desk/SourceInspector'
import { newCommandKey, Sheet } from '@/components/ui'
import { useArtifact, useArtifacts, useCapabilities, useProject } from '@/lib/queries'
import { ErrorNotice, projectHref } from '@/features/execution/feedback'
import { MaterialInspector } from './MaterialInspector'
import { CollectionEditor } from './CollectionEditor'
import { ArtifactPreview } from '@/features/workspace/preview'
import { DeskGrid } from '@/components/ui/Desk'
import { MaterialCard } from './MaterialCard'
import styles from './materials.module.css'

function stableCommand(ref:{current:{key:string,body:string}|null},body:unknown) { const encoded=JSON.stringify(body); if(!ref.current||ref.current.body!==encoded)ref.current={key:newCommandKey(),body:encoded}; return ref.current.key }

export { MaterialCard } from './MaterialCard'
export type { MaterialCardProps } from './MaterialCard'
export type { MaterialsIntegrations } from './MaterialsViews'

/**
 * Capability switch: `workspace_views` → curated views; only `workspace_files` → the existing catalog UI;
 * neither → the artifact fallback.
 */
export function MaterialsScreen({ project_id, integrations }: { project_id: string, integrations?: MaterialsIntegrations }) {
  const router = useRouter(), search = useSearchParams()
  const features = useCatalogFeatures(), catalog = useCatalog(project_id)
  const shared: MaterialsIntegrations = {
    openChat: prompt => window.dispatchEvent(new CustomEvent(CHAT_PROMPT_EVENT, { detail: prompt })),
    addSourceActions: <LiteratureActions project_id={project_id} onOpenSource={id => {
      const query = new URLSearchParams(search.toString())
      for (const key of ['file', 'claim', 'artifact']) query.delete(key)
      query.set('source', id)
      router.push(`${projectHref(project_id)}/materials?${query}`, { scroll: false })
    }} />,
    sourceReader: props => <SourceInspector {...props} />,
    ...integrations,
  }
  if (features.is_loading) return <section className={styles.page}><p role="status" className={styles.empty}>Loading Library…</p></section>
  if (!features.files || !!features.error) return <LegacyMaterialsFallback project_id={project_id} error={features.error} />
  if (catalog.error && (catalog.error as { status?: number }).status === 404) return <LegacyMaterialsFallback project_id={project_id} error={catalog.error} />
  if (features.views) return <MaterialsViews project_id={project_id} integrations={shared} />
  return <FoundationMaterials project_id={project_id} />
}

function FoundationMaterials({ project_id }: { project_id: string }) {
  const search = useSearchParams(), router = useRouter(), project = useProject(project_id), caps = useCapabilities()
  const pageRef = useRef<HTMLElement | null>(null)
  const wideInspector = useWideInspector(pageRef)
  const catalog = useCatalog(project_id), mutation = useCatalogMutation(project_id), tags = useTags(project_id), collections = useCollections(project_id)
  const q=search.get('q')??'', tag=search.get('tag')??'', collection=search.get('collection')??''
  const [sort, setSort] = useState<'name'|'updated_at'|'created_at'>('name')
  const [presentation, setPresentation] = useState<'cards'|'list'>('cards')
  const [status,setStatus]=useState<'active'|'trashed'|'all'>('active')
  const [selectedIds, setSelectedIds] = useState<string[]>([]), [draftName, setDraftName] = useState(''), [draftContent, setDraftContent] = useState(''), [newMime, setNewMime] = useState<'text/markdown'|'text/plain'>('text/markdown')
  const [newTag, setNewTag] = useState(''), [newTagLabel, setNewTagLabel] = useState(''), [newCollection, setNewCollection] = useState(''), [dynamic, setDynamic] = useState(false), [collectionFilterTag, setCollectionFilterTag] = useState('')
  const [manage, setManage] = useState(false), [creatingNote, setCreatingNote] = useState(false), [bulkTag, setBulkTag] = useState('')
  const noteCommand = useRef<{ key:string, body:{name:string,content:string,mime_type:'text/markdown'|'text/plain'} }|null>(null)
  const tagCommand = useRef<{key:string,body:unknown}|null>(null), collectionCommand=useRef<{key:string,body:unknown}|null>(null)
  const extraCommands=useRef(new Map<string,{key:string,body:string}>())
  const selected = search.get('file') ?? ''
  const inspectorOpener = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (selected || !inspectorOpener.current) return
    const opener = inspectorOpener.current
    const frame = requestAnimationFrame(() => { if (opener.isConnected) opener.focus() })
    return () => cancelAnimationFrame(frame)
  }, [selected])
  const filters = useMemo(()=>({ q: q.trim() || undefined, tags: tag ? [tag] : undefined, collection_id: collection || undefined, sort, order:sort==='name'?'asc' as const:'desc' as const, status, limit:50 }),[q,tag,collection,sort,status])
  const files = useFiles(project_id, filters)
  const archived = project.data?.status === 'archived'
  const protectedSelection = files.items.some(f=>selectedIds.includes(f.id)&&f.tags.some(t=>t.slug===bulkTag&&t.assigned_by==='system'))
  const enabled = Boolean((caps.data?.features as Record<string, unknown>|undefined)?.workspace_files)
  const setParam = (key:string,value:string|null) => { const p=new URLSearchParams(search.toString()); if(value) p.set(key,value); else p.delete(key); router.replace(`${projectHref(project_id)}/materials${p.size?`?${p}`:''}`,{scroll:false}) }
  function select(id:string) { inspectorOpener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; const p=new URLSearchParams(search.toString()); p.delete('source');p.delete('claim');p.delete('artifact');p.set('file',id);router.replace(`${projectHref(project_id)}/materials?${p}`,{scroll:false}) }
  const originType=search.get('source')?'source' as const:search.get('claim')?'claim' as const:search.get('artifact')?'artifact' as const:null
  const originId=originType?search.get(originType):null
  // Bounded lookup independent of the browse filters; never pages through the filtered list.
  const origin=useOriginFile(project_id,originType,originId)
  const matchId=origin.file?.id
  useEffect(()=>{
    if(!originId||!enabled||selected||!matchId)return
    const p=new URLSearchParams(search.toString());p.delete('source');p.delete('claim');p.delete('artifact');p.set('file',matchId);router.replace(`${projectHref(project_id)}/materials?${p}`,{scroll:false})
  },[originId,enabled,selected,matchId,router,project_id,search])
  const resolvingOrigin=Boolean(originId&&!selected&&!matchId&&origin.is_loading)
  const missingOrigin=Boolean(originId&&!selected&&!matchId&&origin.missing)
  const originLookupError=Boolean(originId&&!selected&&!matchId&&origin.error)
  const createNote = async(e:React.FormEvent) => { e.preventDefault(); if(archived || !draftName.trim())return; const body={name:draftName.trim(),content:draftContent,mime_type:newMime}; if(!noteCommand.current||JSON.stringify(noteCommand.current.body)!==JSON.stringify(body))noteCommand.current={key:newCommandKey(),body}; try { const r=await mutation.mutateAsync(()=>catalogApi.createNote(project_id,body,{idempotency_key:noteCommand.current!.key})) as {data?:WorkspaceFile}; const file=r?.data;setDraftName('');setDraftContent('');noteCommand.current=null;setCreatingNote(false);if(file)select(file.id);await files.refetch() } catch { /* Keep the same note draft and command key for a safe retry. */ } }
  const makeTag = async(e:React.FormEvent) => { e.preventDefault(); if(!newTag.trim())return; const slug=newTag.trim().toLowerCase().replace(/\s+/g,'-'), body={slug,label:newTagLabel.trim()||newTag.trim()}; if(!tagCommand.current||JSON.stringify(tagCommand.current.body)!==JSON.stringify(body))tagCommand.current={key:newCommandKey(),body}; try { await mutation.mutateAsync(()=>catalogApi.createTag(project_id,body,{idempotency_key:tagCommand.current!.key}));tagCommand.current=null;setNewTag('');setNewTagLabel('');await tags.refetch() } catch { /* Error remains visible beside the management controls; retry uses the same command key. */ } }
  const makeCollection = async(e:React.FormEvent) => { e.preventDefault(); if(!newCollection.trim())return; const filter=dynamic?{tags:collectionFilterTag?[collectionFilterTag]:undefined,status:'active' as const}:null, body={name:newCollection.trim(),filter}; if(!collectionCommand.current||JSON.stringify(collectionCommand.current.body)!==JSON.stringify(body))collectionCommand.current={key:newCommandKey(),body}; try { await mutation.mutateAsync(()=>catalogApi.createCollection(project_id,body,{idempotency_key:collectionCommand.current!.key}));collectionCommand.current=null;setNewCollection('');await collections.refetch() } catch { /* Error remains visible beside the management controls; retry uses the same command key. */ } }
  const bulkTagging = async(add:boolean) => { if(!selectedIds.length||!bulkTag)return; const body={file_ids:selectedIds,...(add?{add:[bulkTag]}:{remove:[bulkTag]})}, slot='bulk-tag'; let cmd=extraCommands.current.get(slot); const encoded=JSON.stringify(body); if(!cmd||cmd.body!==encoded){cmd={key:newCommandKey(),body:encoded};extraCommands.current.set(slot,cmd)} try { await mutation.mutateAsync(()=>catalogApi.tagFiles(project_id,body,{idempotency_key:cmd!.key}));extraCommands.current.delete(slot);setSelectedIds([]);await files.refetch() } catch { /* Error remains visible beside the selection; retry uses the same key. */ } }
  const toggleSelect=(id:string)=>setSelectedIds(v=>v.includes(id)?v.filter(x=>x!==id):[...v,id])
  if(!caps.is_loading && (!enabled || !!caps.error)) return <LegacyMaterialsFallback project_id={project_id} error={caps.error} />
  if(catalog.error && (catalog.error as {status?:number}).status===404) return <LegacyMaterialsFallback project_id={project_id} error={catalog.error} />
  return <section ref={pageRef} className={styles.page}>
    <header className={styles.heading}><div><h1>Library</h1><p>One catalog for evidence, research records, outputs, and your notes. Notes and organizational labels never become scientific evidence.</p><p className={styles.meta}>Curated views (Recent, Sources, Media &amp; data, and saved presentations) are unavailable on this backend. The catalog below remains fully usable.</p></div><div className={styles.actions}><button type="button" disabled={archived} onClick={()=>setCreatingNote(v=>!v)}>{creatingNote?'Close note':'New note'}</button><button type="button" onClick={()=>setManage(v=>!v)}>{manage?'Close tools':'Tags & collections'}</button></div></header>
    <div className={styles.toolbar}>
      <label>Search names only<input type="search" value={q} onChange={e=>setParam('q',e.target.value||null)} placeholder="Search names" /></label>
      <div className={styles.presentation} role="group" aria-label="Library presentation"><button type="button" aria-pressed={presentation==='cards'} onClick={()=>setPresentation('cards')}>Cards</button><button type="button" aria-pressed={presentation==='list'} onClick={()=>setPresentation('list')}>List</button></div>
      <details className={styles.filters}><summary>Filters{(tag || collection || status !== 'active') ? ' · active' : ''}</summary><div className={styles.filterFields}>
      <label>Tag filter<select value={tag} onChange={e=>setParam('tag',e.target.value||null)}><option value="">All tags</option>{tags.items.map(t=><option key={t.slug} value={t.slug}>{t.label}</option>)}</select></label>
      <label>Collection<select value={collection} onChange={e=>setParam('collection',e.target.value||null)}><option value="">All items</option>{collections.items.map(c=><option key={c.id} value={c.id}>{c.name}{c.filter?' · saved filter':''}</option>)}</select></label>
      <label>Sort<select value={sort} onChange={e=>setSort(e.target.value as typeof sort)}><option value="name">Name</option><option value="updated_at">Recently updated</option><option value="created_at">Date added</option></select></label>
      <label>Show<select value={status} onChange={e=>setStatus(e.target.value as typeof status)}><option value="active">Active</option><option value="trashed">Trash</option><option value="all">Active + trash</option></select></label>      </div></details>
    </div>
    {(tag || collection || status !== 'active') && <div className={styles.filterSummary}><span>{[tag ? `Tag: ${tags.items.find(t=>t.slug===tag)?.label ?? tag}` : '', collection ? `Collection: ${collections.items.find(c=>c.id===collection)?.name ?? 'selected'}` : '', status !== 'active' ? status === 'all' ? 'Including trash' : 'Trash' : ''].filter(Boolean).join(' · ')}</span><button onClick={()=>{const p=new URLSearchParams(search.toString());p.delete('tag');p.delete('collection');setStatus('active');setSort('name');setSelectedIds([]);router.replace(`${projectHref(project_id)}/materials${p.size?`?${p}`:''}`,{scroll:false})}}>Clear filters</button></div>}
    <ErrorNotice error={catalog.error ?? tags.error ?? collections.error} />
    {(tags.error || collections.error || catalog.error) && <button onClick={() => { void tags.refetch(); void collections.refetch(); void catalog.refetch() }}>Retry organization data</button>}
    {(tags.has_next_page || collections.has_next_page) && <div className={styles.actions}>
      {tags.has_next_page && <button disabled={tags.is_fetching_next_page} onClick={() => void tags.load_next_page()}>Load more tags</button>}
      {collections.has_next_page && <button disabled={collections.is_fetching_next_page} onClick={() => void collections.load_next_page()}>Load more collections</button>}
    </div>}
    {manage && <section className={styles.record}>
      <div className={styles.layout}>
        <section><h2>Tag management</h2><form className={styles.inline} onSubmit={e=>void makeTag(e)}><input aria-label="Tag slug" value={newTag} onChange={e=>setNewTag(e.target.value)} placeholder="new-tag" /><input aria-label="Tag label" value={newTagLabel} onChange={e=>setNewTagLabel(e.target.value)} placeholder="Display label" /><button disabled={archived||mutation.isPending}>Create tag</button></form>{tags.items.map(t=><div key={t.slug}><p>{t.label} · {t.file_count} files {t.system?'· default tag':''}</p><details><summary>Edit label and color</summary><form className={styles.inline} onSubmit={e=>{e.preventDefault();const fd=new FormData(e.currentTarget);void mutation.mutateAsync(()=>catalogApi.editTag(project_id,t.slug,{label:String(fd.get('label')),color:String(fd.get('color'))||null},{etag:`"${t.revision}"`})).then(()=>tags.refetch()).catch(()=>{})}}><input name="label" aria-label={`Label for ${t.slug}`} defaultValue={t.label}/><input name="color" type="color" aria-label={`Color for ${t.slug}`} defaultValue={t.color??'#758393'}/><button disabled={archived}>Save</button></form></details>{!t.system&&<button type="button" disabled={archived} onClick={()=>{if(window.confirm(`Delete tag “${t.label}” and remove its user assignments?`))void mutation.mutateAsync(()=>catalogApi.deleteTag(project_id,t.slug,{etag:`"${t.revision}"`})).then(()=>tags.refetch()).catch(()=>{})}}>Delete</button>}</div>)}</section>
        <section><h2>Collections</h2><form className={styles.form} onSubmit={e=>void makeCollection(e)}><label>Collection name<input value={newCollection} onChange={e=>{setNewCollection(e.target.value);collectionCommand.current=null}} /></label><label><input type="checkbox" checked={dynamic} onChange={e=>{setDynamic(e.target.checked);collectionCommand.current=null}} /> Save as a dynamic filter</label>{dynamic&&<label>Require tag<select value={collectionFilterTag} onChange={e=>{setCollectionFilterTag(e.target.value);collectionCommand.current=null}}><option value="">No tag constraint</option>{tags.items.map(t=><option key={t.slug} value={t.slug}>{t.label}</option>)}</select></label>}<button disabled={archived||mutation.isPending}>Create collection</button></form>{collections.items.map(c=><div key={c.id}><p><strong>{c.name}</strong> · {c.file_count} items · {c.filter?'saved filter':'explicit membership'}</p><CollectionEditor project_id={project_id} collection={c} archived={archived} />{!c.filter&&selectedIds.length>0&&<button disabled={archived} onClick={()=>{const body={file_ids:selectedIds};const key=stableCommand({current:extraCommands.current.get(`collection:${c.id}`)??null},body);extraCommands.current.set(`collection:${c.id}`,{key,body:JSON.stringify(body)});void mutation.mutateAsync(()=>catalogApi.addCollectionFiles(project_id,c.id,selectedIds,{idempotency_key:key})).then(()=>{extraCommands.current.delete(`collection:${c.id}`);return collections.refetch()}).catch(()=>{})}}>Add selection</button>}<button disabled={archived} onClick={()=>{if(window.confirm(`Delete collection “${c.name}”? Files and evidence will stay in the Library.`))void mutation.mutateAsync(()=>catalogApi.deleteCollection(project_id,c.id,{etag:`"${c.revision}"`})).then(()=>collections.refetch()).catch(()=>{})}}>Delete collection</button></div>)}</section>
      </div>
    </section>}
    <div className={`${styles.layout} ${selected ? (wideInspector === false ? styles.catalogOnly : styles.layoutWide) : styles.catalogOnly}`}>
      <section className={styles.list} aria-label="Library catalog">
        <header className={styles.listHeader}><h2>Catalog</h2><span>{files.items.length}{files.has_next_page?' +':''}</span></header>
        {creatingNote&&<form className={styles.form} onSubmit={e=>void createNote(e)} style={{padding:12}}><label>New note title<input value={draftName} onChange={e=>{setDraftName(e.target.value);noteCommand.current=null}} placeholder="Research note.md" /></label><label>Format<select value={newMime} onChange={e=>{setNewMime(e.target.value as typeof newMime);noteCommand.current=null}}><option value="text/markdown">Markdown</option><option value="text/plain">Plain text</option></select></label><label>Content<textarea value={draftContent} onChange={e=>{setDraftContent(e.target.value);noteCommand.current=null}} rows={5} /></label><button disabled={!draftName.trim()||archived||mutation.isPending}>Create note</button></form>}
        {selectedIds.length>0&&<div className={styles.inline} style={{padding:10}}><select aria-label="Bulk tag" value={bulkTag} onChange={e=>setBulkTag(e.target.value)}><option value="">Choose tag</option>{tags.items.map(t=><option key={t.slug} value={t.slug}>{t.label}</option>)}</select><button disabled={!bulkTag||archived} onClick={()=>void bulkTagging(true)}>Add tag</button><button disabled={!bulkTag||archived||protectedSelection} title={protectedSelection?'Recorded tag assignments cannot be removed':undefined} onClick={()=>void bulkTagging(false)}>Remove tag</button><button onClick={()=>setSelectedIds([])}>Clear selection</button></div>}
        <ErrorNotice error={files.error} />{files.is_loading&&<p role="status" className={styles.empty}>Loading catalog…</p>}{!files.is_loading&&!files.items.length&&<p className={styles.empty}>No items match this view. Clear a filter or create a note to get started.</p>}
        {presentation==='cards' ? <DeskGrid>{files.items.map(f=><li key={f.id} className={styles.cardEntry}><label className={styles.cardSelect}><input type="checkbox" checked={selectedIds.includes(f.id)} onChange={()=>toggleSelect(f.id)} aria-label={`Select ${f.name}`} /> Select</label><MaterialCard project_id={project_id} file={f} onInspect={select} selected={selected===f.id} /></li>)}</DeskGrid>
          : <ul className={styles.items}>{files.items.map(f=><li key={f.id} className={styles.itemWrap}><button className={styles.item} type="button" aria-current={selected===f.id?'true':undefined} onClick={()=>select(f.id)}><span className={styles.itemName}>{f.name}</span><span className={styles.meta}>{f.file_kind} · {f.origin?.type??'note'} · {f.scientific_origin??'no scientific origin'} · {f.size_bytes.toLocaleString()} bytes</span><span className={styles.tags}>{f.tags.map(t=><span className={styles.tag} key={t.slug}>{t.slug}</span>)}</span></button><label className={styles.select}><input type="checkbox" checked={selectedIds.includes(f.id)} onChange={()=>toggleSelect(f.id)} aria-label={`Select ${f.name}`} /> Select</label></li>)}</ul>}
        {files.has_next_page&&<div className={styles.empty}><button disabled={files.is_fetching_next_page} onClick={()=>void files.load_next_page()}>{files.is_fetching_next_page?'Loading…':'Load more'}</button></div>}
      </section>
      {selected && wideInspector !== false && <MaterialInspector key={selected} project_id={project_id} file_id={selected} onClose={()=>setParam('file',null)} />}
    </div>
    {selected && wideInspector === false && <Sheet open onClose={()=>setParam('file',null)} title="Material details"><MaterialInspector key={selected} project_id={project_id} file_id={selected} onClose={()=>setParam('file',null)} /></Sheet>}
    {resolvingOrigin&&<p role="status">Finding the linked {originType} in the catalog…</p>}
    {missingOrigin&&<p role="status">{origin.bounded?'The linked item was not found among the first 100 catalog entries of its type. This backend does not support exact link lookup; search for it by name.':'The linked item is not present in the active catalog. It may be unavailable in this project.'}</p>}{originLookupError&&<p role="status">The catalog could not finish finding the linked item. Retry after the connection recovers.</p>}
    <ErrorNotice error={mutation.error} />
  </section>
}

function useWideInspector(root: { current: HTMLElement | null }) {
  const [wide, setWide] = useState(false)
  useEffect(() => {
    if (!root.current || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => setWide(entry.contentRect.width >= 1008))
    observer.observe(root.current)
    return () => observer.disconnect()
  }, [root])
  return wide
}

function LegacyMaterialsFallback({project_id,error}:{project_id:string,error:unknown}) {
  const [selected,setSelected]=useState(''), [needle,setNeedle]=useState('')
  const artifacts=useArtifacts(project_id), artifact=useArtifact(project_id,selected||null)
  const visible=artifacts.items.filter(a=>!needle.trim()||a.filename.toLowerCase().includes(needle.trim().toLowerCase()))
  return <section className={styles.page}><header className={styles.heading}><div><h1>Library</h1><p>The catalog feature is unavailable on this backend. Existing artifact files remain browseable, and project work continues through the available tools.</p></div></header><ErrorNotice error={error}/><p className={styles.actions}><Link href={`${projectHref(project_id)}/research`}>Research</Link><Link href={`${projectHref(project_id)}/studio`}>Experiments</Link><Link href={`${projectHref(project_id)}/runs`}>Run tracker</Link></p><div className={styles.layout}><section className={styles.list}><header className={styles.listHeader}><h2>Saved artifacts</h2></header><label className={styles.body}>Search names only<input type="search" value={needle} onChange={e=>setNeedle(e.target.value)}/></label><ul className={styles.items}>{visible.map(a=><li key={a.id}><button className={styles.item} onClick={()=>setSelected(a.id)} aria-current={selected===a.id?'true':undefined}><span className={styles.itemName}>{a.filename}</span><span className={styles.meta}>{a.kind} · {a.origin} · {a.size_bytes.toLocaleString()} bytes</span></button></li>)}</ul>{artifacts.has_next_page&&<div className={styles.empty}><button onClick={()=>void artifacts.load_next_page()}>Load more artifacts</button></div>}</section><section className={styles.inspector}>{artifact.data?<><h2>{artifact.data.filename}</h2><p className={styles.meta}>{artifact.data.kind} · {artifact.data.origin} · {artifact.data.mime_type}</p><ArtifactPreview project_id={project_id} artifact={artifact.data}/></>:selected?<p className={styles.empty}>Loading artifact…</p>:<p className={styles.empty}>Select an artifact to preview.</p>}</section></div></section>
}
