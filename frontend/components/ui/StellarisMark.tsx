import type { SVGProps } from "react";
import { useId } from "react";

/** Four rotated S-shaped bolts preserve the open spacing of the original sketch. */
export function StellarisMark(props: SVGProps<SVGSVGElement>) {
  const opening = useId();
  return (
    <svg width="36" height="36" viewBox="0 0 96 96" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>
      <defs>
        <clipPath id={opening}>
          <path clipRule="evenodd" d="M0 0H96V96H0ZM54 48A6 6 0 1 0 42 48A6 6 0 1 0 54 48Z" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${opening})`}>
      {Array.from({ length: 4 }, (_, index) => (
        <path key={index} transform={`rotate(${index * 45} 48 48)`} d="M35 7L40 34C41 42 45 45 53 41C60 37 66 43 62 49C58 55 38 41 34 47C30 53 36 59 43 55C51 51 55 54 56 62L61 89" />
      ))}
      </g>
    </svg>
  );
}
