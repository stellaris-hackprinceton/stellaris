// Single inline icon set owned by Agent A (no dependency). 20px stroke icons, decorative only:
// callers supply accessible text (IconButton label or adjacent text).
import type { SVGProps } from "react";

function Svg({ children, ...rest }: SVGProps<SVGSVGElement>) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>
      {children}
    </svg>
  );
}

export const CloseIcon = () => <Svg><path d="M18 6 6 18M6 6l12 12" /></Svg>;
export const MenuIcon = () => <Svg><path d="M4 6h16M4 12h16M4 18h16" /></Svg>;
export const ChatIcon = () => <Svg><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" /></Svg>;
export const SendIcon = () => <Svg><path d="m22 2-7 20-4-9-9-4 20-7Z" /></Svg>;
export const PlusIcon = () => <Svg><path d="M12 5v14M5 12h14" /></Svg>;
export const PaperclipIcon = () => <Svg><path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7" /></Svg>;
export const ExternalIcon = () => <Svg><path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6" /></Svg>;
export const ArrowDownIcon = () => <Svg><path d="M12 5v14M5 12l7 7 7-7" /></Svg>;
export const ResearchIcon = () => <Svg><path d="M4 5h6a3 3 0 0 1 3 3v12a4 4 0 0 0-4-2H4V5Zm16 0h-4a3 3 0 0 0-3 3m7-3v13h-3" /></Svg>;
export const MaterialsIcon = () => <Svg><path d="M4 4h6l2 3h8v13H4V4Z" /><path d="M4 10h16" /></Svg>;
export const ExperimentIcon = () => <Svg><path d="M9 3h6m-5 0v7L4 20h16l-6-10V3M7 15h10" /></Svg>;
export const GraphIcon = () => <Svg><circle cx="6" cy="6" r="3" /><circle cx="18" cy="8" r="3" /><circle cx="10" cy="19" r="3" /><path d="m9 6 6 1M7 9l2 7m7-6-4 6" /></Svg>;
export const TrackerIcon = () => <Svg><path d="M8 5h12M8 12h12M8 19h12" /><circle cx="4" cy="5" r="1" /><circle cx="4" cy="12" r="1" /><circle cx="4" cy="19" r="1" /></Svg>;
export const MoreIcon = () => <Svg><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></Svg>;
export const SunIcon = () => <Svg><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></Svg>;
export const MoonIcon = () => <Svg><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /></Svg>;
export const SystemThemeIcon = () => <Svg><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></Svg>;
