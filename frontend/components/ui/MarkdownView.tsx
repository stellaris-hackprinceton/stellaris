/* eslint-disable @next/next/no-img-element -- Artifact images need session cookies the image optimizer cannot forward. */
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import type { ReactNode } from "react";
import { hrefs } from "@/components/shell/hrefs";
import styles from "./ui.module.css";
import { cx } from "./cx";
import { describeResourceId, humanizeName, isKnownName, isMachineName } from "./scienceLabels";

export type MarkdownViewProps = {
  markdown: string;
  className?: string;
  /** Enables links for resource IDs (`art_…`, `run_…`, `exp_…`) to their project pages. */
  projectId?: string;
};

type HastNode = { type: string; value?: string; tagName?: string; children?: HastNode[] };
const textOf = (node?: HastNode): string =>
  !node ? "" : node.type === "text" ? node.value ?? "" : (node.children ?? []).map(textOf).join("");
const isPlainText = (node?: HastNode) => !!node && (node.children ?? []).every((c) => c.type === "text");

const NUMBER = /^(?:[−-]?\d[\d,]*(?:\.\d+)?(?:e[-+]?\d+)?|—|-)$/i;
const UNCERTAINTY = /^(±\s*\S+)\s*\(([\s\S]+)\)$/;
const STATUS = /^(valid|missing|rejected):\s*([\s\S]+)$/;

// remark-math marks math as <code class="language-math math-inline|math-display">. Keep those classes
// through sanitizing so KaTeX, which runs afterwards on the sanitized tree, can typeset them.
const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), ["className", /^language-./, "math-inline", "math-display"]],
  },
};
const katexOptions = { throwOnError: false, errorColor: "var(--color-danger)", strict: "ignore" as const };

const FENCED_OR_INLINE_CODE = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g;
const DISPLAY_MATH = /\\\[([\s\S]+?)\\\]/g; // \[ … \]
const INLINE_MATH = /\\\(([\s\S]+?)\\\)/g; // \( … \)

/**
 * Agents often write LaTeX with \( … \) and \[ … \] delimiters, which Markdown reads as escaped
 * brackets. Rewrite them to $…$ and $$…$$ everywhere except code spans and fenced code blocks.
 */
export function normalizeMathDelimiters(markdown: string) {
  return markdown.split(FENCED_OR_INLINE_CODE).map((part, i) => i % 2 ? part : part
    .replace(DISPLAY_MATH, (_, tex: string) => `\n$$\n${tex.trim()}\n$$\n`)
    .replace(INLINE_MATH, (_, tex: string) => `$${tex.trim()}$`)).join("");
}

// Project file images load; everything else needs an http(s), mailto, same-site or anchor URL.
function safeUrl(url: string, key: string) {
  if (key === "src") return /^\/api\/v1\/projects\/[^/]+\/artifacts\/[^/]+\/content(?:\?|$)/.test(url) ? url : "";
  return /^(https?:\/\/|mailto:|\/[^/]|#)/i.test(url) ? url : "";
}

function idHref(projectId: string, prefix: string, id: string) {
  if (prefix === "art") return hrefs.artifact(projectId, id);
  if (prefix === "run") return hrefs.run(projectId, id);
  if (prefix === "exp") return hrefs.studio(projectId, id);
  return null;
}

function components(projectId?: string): Components {
  return {
    a: ({ href, children }) => <a href={href} rel="noopener noreferrer">{children}</a>,
    img: ({ src, alt }) => typeof src === "string" && src
      ? <img src={src} alt={alt ?? "Research figure"} loading="lazy" />
      : <span>Image unavailable in this preview</span>,
    // Wide tables scroll inside their own labelled region instead of squeezing every column.
    table: ({ children }) => (
      <div className={styles.mdTable} role="region" aria-label="Table" tabIndex={0}><table>{children}</table></div>
    ),
    td: ({ node, children }) => {
      const raw = textOf(node as HastNode).trim();
      if (!isPlainText(node as HastNode)) return <td className={raw.length > 48 ? styles.mdWide : undefined}>{children}</td>;
      if (isMachineName(raw) || isKnownName(raw)) return <td className={styles.mdName} title={raw}>{humanizeName(raw)}</td>;
      if (NUMBER.test(raw)) return <td className={styles.mdNum}>{raw}</td>;
      const unc = UNCERTAINTY.exec(raw);
      if (unc) return <td className={styles.mdWide}><span className={styles.mdNum}>{unc[1]}</span><span className={styles.mdNote}>{unc[2]}</span></td>;
      const status = STATUS.exec(raw);
      if (status) return <td className={styles.mdWide}><span>{status[1][0].toUpperCase() + status[1].slice(1)}</span><span className={styles.mdNote}>{status[2]}</span></td>;
      if (raw === "valid" || raw === "unknown" || raw === "observed" || raw === "derived") return <td>{raw[0].toUpperCase() + raw.slice(1)}</td>;
      return <td className={raw.length > 48 ? styles.mdWide : !raw.includes(" ") ? styles.mdTight : undefined}>{children}</td>;
    },
    code: ({ node, className, children }) => {
      const raw = textOf(node as HastNode);
      const id = describeResourceId(raw);
      if (!id) return <code className={className}>{children}</code>;
      const href = projectId ? idHref(projectId, id.prefix, raw) : null;
      const chip: ReactNode = <span className={styles.idChip} title={raw}>{id.label}</span>;
      return href ? <Link href={href} className={styles.idLink} aria-label={`${id.label} (${raw})`}>{chip}</Link> : chip;
    },
  };
}

/**
 * Sanitized GitHub-flavored Markdown. Raw HTML is skipped, links are protocol-limited, and only
 * project file images load. LaTeX math is typeset with KaTeX. Tables use reader-facing names; the
 * original text stays in a title.
 */
export function MarkdownView({ markdown, className, projectId }: MarkdownViewProps) {
  return (
    <div className={cx(styles.markdown, className)}>
      <ReactMarkdown skipHtml remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeSanitize, schema], [rehypeKatex, katexOptions]]} urlTransform={safeUrl} components={components(projectId)}>
        {normalizeMathDelimiters(markdown)}
      </ReactMarkdown>
    </div>
  );
}
