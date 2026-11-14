"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { ID } from "@/contracts/api";
import { useEditProject, useProject } from "@/lib/queries";
import {
  Button, ChatIcon, Dialog, ErrorNotice, IconButton, MenuIcon, Skeleton, StatusBadge, describeError,
} from "@/components/ui";
import { MoreIcon } from "@/components/ui/icons";
import { ConnectionStatus } from "./ConnectionStatus";
import { VIEWS, currentView } from "./ProjectNavigation";
import { hrefs } from "./hrefs";
import styles from "./shell.module.css";

type Props = {
  project_id: ID;
  showMenuButton: boolean;
  onOpenMenu: () => void;
  chatOpen: boolean;
  onToggleChat: () => void;
  terminalOpen: boolean;
  onToggleTerminal: () => void;
};

export function ProjectHeader({ project_id, showMenuButton, onOpenMenu, chatOpen, onToggleChat, terminalOpen, onToggleTerminal }: Props) {
  const project = useProject(project_id);
  const view = currentView(usePathname() ?? "", project_id);
  const viewLabel = VIEWS.find((v) => v.id === view)?.label;
  const archived = project.data?.status === "archived";

  return (
    <header className={styles.header}>
      {showMenuButton && <IconButton label="Open project menu" icon={<MenuIcon />} onClick={onOpenMenu} />}
      <div className={styles.headerTitle}>
        {project.data ? (
          <h1 className={styles.projectName} title={project.data.name}>{project.data.name}</h1>
        ) : project.error ? (
          <h1 className={styles.projectName}>Project unavailable</h1>
        ) : (
          <Skeleton width="12rem" height="1.5rem" />
        )}
        {viewLabel && <span className={styles.viewLabel}><span aria-hidden="true">/</span> {viewLabel}</span>}
        {archived && <StatusBadge tone="warning">Archived</StatusBadge>}
      </div>
      <div className={styles.headerActions}>
        <ConnectionStatus />
        <Button
          aria-label={chatOpen ? "Hide research chat" : "Show research chat"}
          aria-pressed={chatOpen}
          className={styles.chatToggle}
          onClick={onToggleChat}
        ><ChatIcon /><span>Chat</span></Button>
        <Button
          id="terminal-toggle"
          aria-label={terminalOpen ? "Hide terminal" : "Show terminal"}
          aria-pressed={terminalOpen}
          className={styles.chatToggle}
          onClick={onToggleTerminal}
        ><span aria-hidden="true" className={styles.terminalGlyph}>&gt;_</span><span>Terminal</span></Button>
        <details className={styles.projectMenu}>
          <summary aria-label="Project actions" title="Project actions"><MoreIcon /></summary>
          <div className={styles.menuPanel}>
            <Link href={hrefs.projects()}>All projects</Link>
            {project.data && <ArchiveControl project_id={project_id} archived={archived} etag={project.etag} />}
          </div>
        </details>
      </div>
    </header>
  );
}

function ArchiveControl({ project_id, archived, etag }: { project_id: ID; archived: boolean; etag: string | null }) {
  const edit = useEditProject(project_id);
  const [confirming, setConfirming] = useState(false);

  async function apply() {
    if (!etag) return;
    try {
      await edit.mutateAsync({ body: { status: archived ? "active" : "archived" }, etag });
      setConfirming(false);
    } catch { /* shown below */ }
  }

  return (
    <>
      <Button onClick={() => { edit.reset(); setConfirming(true); }} disabled={!etag}>
        {archived ? "Restore" : "Archive"}
      </Button>
      <Dialog open={confirming} onClose={() => setConfirming(false)} title={archived ? "Restore project?" : "Archive project?"}>
        <p className="prose">
          {archived
            ? "Restoring re-enables chat, uploads, experiment edits and new runs."
            : "Archiving keeps everything readable but blocks chat, uploads, experiment edits and new runs. Runs already accepted can still finish or be cancelled. You can restore it later."}
        </p>
        {edit.error != null && (
          <ErrorNotice {...describeError(edit.error, "The project was not changed")}
            message={(edit.error as { code?: string }).code === "REVISION_CONFLICT"
              ? "The project changed elsewhere. Close this dialog and try again with the latest version."
              : describeError(edit.error).message} />
        )}
        <div className={styles.dialogActions}>
          <Button variant={archived ? "primary" : "danger"} pending={edit.isPending} onClick={apply}>
            {archived ? "Restore" : "Archive"}
          </Button>
          <Button onClick={() => setConfirming(false)}>Cancel</Button>
        </div>
      </Dialog>
    </>
  );
}
