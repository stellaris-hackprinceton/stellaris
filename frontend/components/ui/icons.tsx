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
