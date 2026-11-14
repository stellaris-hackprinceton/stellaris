"use client";
import { useState } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import type { ID } from "@/contracts/api";
import { Sheet } from "@/components/ui";
import { useChatDraft } from "@/features/research/chat/ChatComposer";
import { ResearchChat } from "@/features/research/chat";
import { ProjectHeader } from "./ProjectHeader";
import { ProjectNavigation } from "./ProjectNavigation";
import { useMediaQuery } from "./useMediaQuery";
import { useStoredFlag } from "./useStoredFlag";
import styles from "./shell.module.css";

export type ProjectShellProps = {
  project_id: ID;
  children: ReactNode;
};

/**
 * Project frame: navigation, header and the single ResearchChat instance.
 * ≥1280px: sidebar + content + collapsible chat rail. 768–1279px: sidebar, chat in a side sheet.
 * <768px: navigation in a menu sheet, chat in a full-height sheet.
 */
export function ProjectShell(props: ProjectShellProps) {
  return <ProjectShellBody key={props.project_id} {...props} />;
}

function ProjectShellBody({ project_id, children }: ProjectShellProps) {
  const chatDraft = useChatDraft();
  const wide = useMediaQuery("(min-width: 1280px)", true);
  const narrow = useMediaQuery("(max-width: 767px)", false);
  const [railOpen, setRailOpen] = useStoredFlag("stellaris.chatRailOpen", true);
  const [chatSheet, setChatSheet] = useState(false);
  // The menu belongs to the path it was opened on, so navigating closes it without an effect.
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const pathname = usePathname() ?? "";

  // Overlays only exist in the layouts that use them.
  const sheetOpen = !wide && chatSheet;
  const menuOpen = narrow && menuPath === pathname;
  const setSheetOpen = setChatSheet;
  const setMenuOpen = (open: boolean) => setMenuPath(open ? pathname : null);

  const chatOpen = wide ? railOpen : sheetOpen;
  const toggleChat = () => (wide ? setRailOpen(!railOpen) : setSheetOpen(!sheetOpen));
  const chat = <ResearchChat draft={chatDraft} project_id={project_id} showHeading={wide} />;

  return (
    <div className={styles.shell} data-chat-rail={wide && railOpen ? "open" : "closed"}>
      <a href="#project-main" className={styles.skipLink}>Skip to content</a>
      {!narrow && (
        <aside className={styles.sidebar}>
          <ProjectNavigation project_id={project_id} />
        </aside>
      )}
      <div className={styles.main}>
        <ProjectHeader
          project_id={project_id}
          showMenuButton={narrow}
          onOpenMenu={() => setMenuOpen(true)}
          chatOpen={chatOpen}
          onToggleChat={toggleChat}
        />
        <main id="project-main" className={styles.content} tabIndex={-1}>{children}</main>
      </div>
      {wide && (
        <aside className={styles.chatRail} aria-label="Research chat" hidden={!railOpen}>{chat}</aside>
      )}
      {!wide && (
        <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Research chat" keepMounted>{chat}</Sheet>
      )}
      {narrow && (
        <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title="Project menu">
          <ProjectNavigation project_id={project_id} onNavigate={() => setMenuOpen(false)} />
        </Sheet>
      )}
    </div>
  );
}
