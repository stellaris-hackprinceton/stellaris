"use client";
import Link from "next/link";
import { useState } from "react";
import type { ID } from "@/contracts/api";
import { useEditProject, useProject } from "@/lib/queries";
import {
  Button, ChatIcon, Dialog, ErrorNotice, IconButton, MenuIcon, Skeleton, StatusBadge, ThemeToggle, describeError,
} from "@/components/ui";
import { MoreIcon } from "@/components/ui/icons";
import { ConnectionStatus } from "./ConnectionStatus";
import { StellarisMark } from "@/components/ui/StellarisMark";
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
  const archived = project.data?.status === "archived";

  return (
    <header className={styles.header}>
      {showMenuButton && <div className={styles.mobileControls}><IconButton label="Open project menu" icon={<MenuIcon />} onClick={onOpenMenu} /><Link href={hrefs.projects()} aria-label="Stellaris projects" className={styles.mobileBrand}><StellarisMark /></Link></div>}
      <div className={styles.headerTitle}>
        {project.data ? (
          <span className={styles.projectName} title={project.data.name}>{project.data.name}</span>
        ) : project.error ? (
          <span className={styles.projectName}>Project unavailable</span>
        ) : (
          <Skeleton width="12rem" height="1.5rem" />
        )}
        {archived && <StatusBadge tone="warning">Archived</StatusBadge>}
      </div>
      <div className={styles.headerActions}>
        <ConnectionStatus />
        <Button
          aria-label={chatOpen ? "Hide Assistant" : "Show Assistant"}
          aria-pressed={chatOpen}
          className={styles.chatToggle}
          onClick={onToggleChat}
        ><ChatIcon /><span>Assistant</span></Button>
        <Button
          id="terminal-toggle"
          aria-label={terminalOpen ? "Hide terminal" : "Show terminal"}
          aria-pressed={terminalOpen}
          className={styles.chatToggle}
          onClick={onToggleTerminal}
        ><span aria-hidden="true" className={styles.terminalGlyph}>&gt;_</span><span>Terminal</span></Button>
        <ThemeToggle className={styles.themeToggle} />
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
