// App icon set, in ChatPlotDB's house style: 14x14 glyphs drawn as filled
// outlines or 1px strokes, plus a 24-box / 1.75-stroke family, so every icon
// reads at the same weight at 18px. Home, Dashboard (Runs), Database, Tools,
// Relay (Feedback) and PanelToggle are copied from ChatPlotDB's
// nav-icons.tsx / panel-toggle.tsx; the rest are drawn to match.
//
// Every icon spreads its props onto the <svg>, so width/height/className
// work as on any SVG. Default size 18px.
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

function Fill14({ children, ...p }: P) {
  return (
    <svg viewBox="0 0 14 14" width={18} height={18} fill="none" aria-hidden {...p}>
      {children}
    </svg>
  );
}

function Stroke24({ children, ...p }: P) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={18}
      height={18}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...p}
    >
      {children}
    </svg>
  );
}

/* ---- copied from ChatPlotDB ------------------------------------------- */

export const IconHome = (p: P) => (
  <Fill14 {...p}>
    <path
      d="M5.41699 1.14917C6.33787 0.395804 7.66213 0.395804 8.58301 1.14917L11.8994 3.86304C12.5957 4.43275 12.9999 5.28467 13 6.18433V9.99976C13 11.6566 11.6569 12.9998 10 12.9998H4C2.34315 12.9998 1 11.6566 1 9.99976V6.18433C1.0001 5.28467 1.40429 4.43275 2.10059 3.86304L5.41699 1.14917ZM7.9502 1.92261C7.39768 1.47063 6.60232 1.47063 6.0498 1.92261L2.7334 4.63647C2.26924 5.01626 2.0001 5.5846 2 6.18433V9.99976C2 11.1043 2.89543 11.9998 4 11.9998H10C11.1046 11.9998 12 11.1043 12 9.99976V6.18433C11.9999 5.5846 11.7308 5.01626 11.2666 4.63647L7.9502 1.92261ZM9.5 8.99976C9.77607 8.99976 9.99989 9.22371 10 9.49976C10 9.7759 9.77614 9.99976 9.5 9.99976H4.5C4.22386 9.99976 4 9.7759 4 9.49976C4.00011 9.22371 4.22393 8.99976 4.5 8.99976H9.5Z"
      fill="currentColor"
    />
  </Fill14>
);

export const IconRuns = (p: P) => (
  <Fill14 {...p}>
    {([[1.5, 1.5], [8, 1.5], [1.5, 8], [8, 8]] as const).map(([x, y]) => (
      <rect key={`${x}-${y}`} x={x} y={y} width="4.5" height="4.5" rx="1.25" stroke="currentColor" strokeWidth="1" />
    ))}
  </Fill14>
);

export const IconDatasets = (p: P) => (
  <Fill14 {...p}>
    <ellipse cx="7" cy="3.5" rx="5" ry="2" stroke="currentColor" strokeWidth="1.1" />
    <path d="M2 3.5v3.25C2 8.05 4.24 9.25 7 9.25s5-1.2 5-2.5V3.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    <path d="M2 6.75V10c0 1.3 2.24 2.5 5 2.5s5-1.2 5-2.5V6.75" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
  </Fill14>
);

export const IconPlug = (p: P) => (
  <Stroke24 {...p}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </Stroke24>
);

export const IconMessage = (p: P) => (
  <Stroke24 {...p}>
    <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.9 8.9 0 0 1-3.6-.8L3 21l1.9-4.6A8.3 8.3 0 0 1 3 11.5a8.4 8.4 0 0 1 9-8.4 8.4 8.4 0 0 1 9 8.4z" />
    <path d="M8.5 11.5h.01" />
    <path d="M12 11.5h.01" />
    <path d="M15.5 11.5h.01" />
  </Stroke24>
);

export const IconPanel = (p: P) => (
  <svg viewBox="0 0 18 18" width={18} height={18} fill="none" aria-hidden {...p}>
    <path
      fill="currentColor"
      d="M12.1797 2.5C12.9275 2.5 13.5188 2.49925 13.9941 2.53809C14.4753 2.5774 14.8819 2.6596 15.2529 2.84863C15.8549 3.15542 16.3446 3.64505 16.6514 4.24707C16.8403 4.618 16.9226 5.02485 16.9619 5.50586C17.0007 5.98111 17 6.57268 17 7.32031V10.6797C17 11.4273 17.0007 12.0189 16.9619 12.4941C16.9226 12.9751 16.8404 13.382 16.6514 13.7529C16.3446 14.3549 15.8549 14.8446 15.2529 15.1514C14.882 15.3404 14.4752 15.4226 13.9941 15.4619C13.5188 15.5007 12.9275 15.5 12.1797 15.5L5.82031 15.5C5.07251 15.5 4.48117 15.5007 4.00586 15.4619C3.52479 15.4226 3.11804 15.3404 2.74707 15.1514C2.1451 14.8446 1.65543 14.3549 1.34863 13.7529C1.15964 13.382 1.07741 12.9751 1.03809 12.4941C0.999258 12.0189 1 11.4273 1 10.6797L1 7.32031C1 6.57268 0.999281 5.98111 1.03809 5.50586C1.07739 5.02485 1.1597 4.618 1.34863 4.24707C1.65539 3.64505 2.14507 3.15542 2.74707 2.84863C3.11807 2.6596 3.52474 2.5774 4.00586 2.53809C4.48117 2.49925 5.07249 2.5 5.82031 2.5L12.1797 2.5ZM5.82031 3.5C5.05599 3.5 4.51206 3.50042 4.08691 3.53516C3.66788 3.56943 3.40764 3.63503 3.20117 3.74023C2.78746 3.95113 2.4511 4.28744 2.24023 4.70117C2.13512 4.9076 2.06941 5.16806 2.03516 5.58691C2.00045 6.01201 2 6.55621 2 7.32031L2 10.6797C2 11.4438 2.00043 11.988 2.03516 12.4131C2.06943 12.8319 2.13506 13.0924 2.24023 13.2988C2.45113 13.7125 2.78749 14.0489 3.20117 14.2598C3.40762 14.3649 3.66797 14.4306 4.08691 14.4648C4.51206 14.4996 5.05601 14.5 5.82031 14.5L7 14.5L7 3.5H5.82031ZM8 14.5H12.1797C12.944 14.5 13.4879 14.4996 13.9131 14.4648C14.332 14.4306 14.5924 14.3649 14.7988 14.2598C15.2125 14.0489 15.5489 13.7125 15.7598 13.2988C15.8649 13.0924 15.9306 12.8319 15.9648 12.4131C15.9996 11.988 16 11.4438 16 10.6797L16 7.32031C16 6.55621 15.9995 6.01201 15.9648 5.58691C15.9306 5.16806 15.8649 4.9076 15.7598 4.70117C15.5489 4.28744 15.2125 3.95113 14.7988 3.74023C14.5924 3.63503 14.3321 3.56943 13.9131 3.53516C13.4879 3.50042 12.944 3.5 12.1797 3.5L8 3.5L8 14.5ZM5.3252 7.5C5.60111 7.50026 5.82519 7.72402 5.8252 8C5.8252 8.27598 5.60111 8.49974 5.3252 8.5H3.97559C3.69944 8.5 3.47559 8.27614 3.47559 8C3.47559 7.72386 3.69944 7.5 3.97559 7.5H5.3252ZM5.34961 5.5C5.62575 5.5 5.84961 5.72386 5.84961 6C5.84961 6.27614 5.62575 6.5 5.34961 6.5H4C3.72386 6.5 3.5 6.27614 3.5 6C3.5 5.72386 3.72386 5.5 4 5.5L5.34961 5.5Z"
    />
  </svg>
);

/* ---- drawn to match ----------------------------------------------------- */

// Two rounded columns, same 14-box / 1px stroke / 1.25 radius as IconRuns.
export const IconCompare = (p: P) => (
  <Fill14 {...p}>
    <rect x="1.5" y="1.5" width="4.75" height="11" rx="1.25" stroke="currentColor" strokeWidth="1" />
    <rect x="7.75" y="1.5" width="4.75" height="11" rx="1.25" stroke="currentColor" strokeWidth="1" />
  </Fill14>
);

export const IconLive = (p: P) => (
  <Stroke24 {...p}>
    <path d="M3 12h3.5l2.5-7 5 14 2.5-7H21" />
  </Stroke24>
);

export const IconSearch = (p: P) => (
  <Stroke24 {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.6-3.6" />
  </Stroke24>
);

export const IconShowcase = (p: P) => (
  <Stroke24 {...p}>
    <path d="m12 3.5 2.6 5.3 5.9.86-4.25 4.14 1 5.86L12 16.9l-5.25 2.76 1-5.86L3.5 9.66l5.9-.86L12 3.5Z" />
  </Stroke24>
);

export const IconBookmark = (p: P) => (
  <Stroke24 {...p}>
    <path d="M7 3.5h10a1.5 1.5 0 0 1 1.5 1.5v15.5L12 16.5l-6.5 4V5A1.5 1.5 0 0 1 7 3.5Z" />
  </Stroke24>
);

export const IconBolt = (p: P) => (
  <Stroke24 {...p}>
    <path d="M13 2.5 4.5 13.5H12l-1 8 8.5-11H12l1-8Z" />
  </Stroke24>
);

export const IconBook = (p: P) => (
  <Stroke24 {...p}>
    <path d="M12 6.5v14" />
    <path d="M3.5 5A1.5 1.5 0 0 1 5 3.5h4A3 3 0 0 1 12 6.5a3 3 0 0 1 3-3h4A1.5 1.5 0 0 1 20.5 5v12a1.5 1.5 0 0 1-1.5 1.5h-4a3 3 0 0 0-3 2 3 3 0 0 0-3-2H5A1.5 1.5 0 0 1 3.5 17V5Z" />
  </Stroke24>
);

export const IconCloud = (p: P) => (
  <Stroke24 {...p}>
    <path d="M7 18.5a4.5 4.5 0 0 1-.5-8.97A6 6 0 0 1 18 9a4.75 4.75 0 0 1-.5 9.5H7Z" />
  </Stroke24>
);

export const IconBranch = (p: P) => (
  <Stroke24 {...p}>
    <circle cx="6" cy="5.5" r="2.25" />
    <circle cx="6" cy="18.5" r="2.25" />
    <circle cx="18" cy="8" r="2.25" />
    <path d="M6 7.75v8.5" />
    <path d="M18 10.25c0 4.25-4.5 5-11.2 6.6" />
  </Stroke24>
);

export const IconPlus = (p: P) => (
  <Stroke24 {...p}>
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </Stroke24>
);

export const IconArrowUp = (p: P) => (
  <Stroke24 strokeWidth={2} {...p}>
    <path d="M12 19V5" />
    <path d="m6 11 6-6 6 6" />
  </Stroke24>
);

export const IconChevronDown = (p: P) => (
  <Stroke24 {...p}>
    <path d="m6 9 6 6 6-6" />
  </Stroke24>
);

export const IconChevronRight = (p: P) => (
  <Stroke24 {...p}>
    <path d="m9 6 6 6-6 6" />
  </Stroke24>
);

export const IconX = (p: P) => (
  <Stroke24 {...p}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </Stroke24>
);
