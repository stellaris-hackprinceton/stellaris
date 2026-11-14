"use client";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import type { ID } from "@/contracts/api";
import { Sheet } from "@/components/ui";
import { useChatDraft } from "@/features/research/chat/ChatComposer";
import { ResearchChat } from "@/features/research/chat";
import { TerminalPanel } from "@/features/terminal";
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
 * One project frame and Assistant draft. The sidebar is CSS-responsive for a stable first paint.
 * From 1360px Assistant docks. Narrower layouts use a sheet, with navigation in a sheet below 768px.
 */
export function ProjectShell(props: ProjectShellProps) {
  return <ProjectShellBody key={props.project_id} {...props} />;
}

function ProjectShellBody({ project_id, children }: ProjectShellProps) {
  const chatDraft = useChatDraft();
  const wide = useMediaQuery("(min-width: 1360px)", false);
  const narrow = useMediaQuery("(max-width: 767px)", false);
  const [railOpen, setRailOpen] = useStoredFlag("stellaris.chatRailOpen", false);
  const [chatSheet, setChatSheet] = useState(false);
  const setChatText = chatDraft.setText;
  useEffect(() => {
    function prefillChat(event: Event) {
      const prompt: unknown = (event as CustomEvent<unknown>).detail;
      if (typeof prompt !== "string" || !prompt.trim()) return;
      setChatText(previous => previous.trim() ? `${previous}\n\n${prompt}` : prompt);
      if (wide) setRailOpen(true);
      else setChatSheet(true);
    }
    window.addEventListener("stellaris:chat-prompt", prefillChat);
    return () => window.removeEventListener("stellaris:chat-prompt", prefillChat);
  }, [wide, setRailOpen, setChatText]);
  // The terminal panel mounts on first open and then stays mounted (hidden) so its session view survives.
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [terminalMounted, setTerminalMounted] = useState(false);
  const toggleTerminal = () => { setTerminalMounted(true); setTerminalOpen(!terminalOpen); };
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
      <aside className={styles.sidebar}>
        <ProjectNavigation project_id={project_id} />
      </aside>
      <div className={styles.main}>
        <ProjectHeader
          project_id={project_id}
          showMenuButton
          onOpenMenu={() => setMenuOpen(true)}
          chatOpen={chatOpen}
          onToggleChat={toggleChat}
          terminalOpen={terminalOpen}
          onToggleTerminal={toggleTerminal}
        />
        <main id="project-main" className={styles.content} tabIndex={-1}>{children}</main>
        {terminalMounted && (
          <TerminalPanel project_id={project_id} open={terminalOpen} onHide={() => { setTerminalOpen(false); document.getElementById("terminal-toggle")?.focus(); }} />
        )}
      </div>
      {wide && (
        <aside className={styles.chatRail} aria-label="Assistant" hidden={!railOpen}>{chat}</aside>
      )}
      {!wide && (
        <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Assistant" keepMounted>{chat}</Sheet>
      )}
      {narrow && (
        <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title="Project menu">
          <ProjectNavigation project_id={project_id} onNavigate={() => setMenuOpen(false)} />
        </Sheet>
      )}
    </div>
  );
}
