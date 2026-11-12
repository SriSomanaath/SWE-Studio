"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type SVGProps, useEffect, useState } from "react";

import { AuthorMenu } from "@/components/AuthorMenu";
import {
  IconBolt,
  IconBook,
  IconBookmark,
  IconChevronDown,
  IconCloud,
  IconCompare,
  IconDatasets,
  IconHome,
  IconLive,
  IconMessage,
  IconPanel,
  IconPlug,
  IconRuns,
  IconSearch,
  IconShowcase,
} from "@/components/Icons";
import { UserMenu } from "@/components/UserMenu";
import { cn } from "@/lib/cn";

const REPO = "https://github.com/SriSomanaath/SWE-Studio";

type Item = { href: string; label: string; icon: (p: SVGProps<SVGSVGElement>) => React.ReactNode };

const PRIMARY: Item[] = [
  { href: "/", label: "Home", icon: IconHome },
  { href: "/runs", label: "Runs", icon: IconRuns },
  { href: "/live", label: "Live", icon: IconLive },
  { href: "/compare", label: "Compare", icon: IconCompare },
  { href: "/search", label: "Search", icon: IconSearch },
  { href: "/datasets", label: "Datasets", icon: IconDatasets },
];

const TOOLS: Item[] = [
  { href: "/showcase", label: "Showcase", icon: IconShowcase },
  { href: "/bookmarks", label: "Bookmarks", icon: IconBookmark },
  { href: "/integrations", label: "Integrations", icon: IconPlug },
  { href: "/webhooks", label: "Webhooks", icon: IconBolt },
];

// Routes that render without the app chrome.
const BARE = ["/login"];

const CANVAS = "bg-[hsl(var(--canvas))]";

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" || pathname.startsWith("/agent") : pathname.startsWith(href);
}

/** Boolean persisted in localStorage; `fallback` decides when nothing is stored. */
function useStoredFlag(key: string, fallback: () => boolean) {
  const [value, setValue] = useState(true);
  useEffect(() => {
    const stored = window.localStorage.getItem(key);
    setValue(stored === null ? fallback() : stored === "1");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const set = (v: boolean) => {
    setValue(v);
    window.localStorage.setItem(key, v ? "1" : "0");
  };
  return [value, set] as const;
}

function NavLink({ item, pathname, onNavigate }: { item: Item; pathname: string; onNavigate: () => void }) {
  const active = isActive(pathname, item.href);
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex h-9 items-center gap-2.5 rounded-xl px-2.5 text-[15px] font-medium tracking-[-0.28px]",
        "transition-[background-color,color,box-shadow] duration-200 ease-out-soft",
        "outline-none focus-visible:ring-2 focus-visible:ring-foreground/15",
        active
          ? "bg-background text-foreground shadow-[0_1px_2px_rgba(0,0,0,0.06),0_0_0_1px_rgba(0,0,0,0.02)]"
          : "text-muted-foreground hover:bg-foreground/[0.045] hover:text-foreground",
      )}
    >
      <Icon
        className={cn(
          "size-[18px] shrink-0 transition-colors duration-200",
          active ? "text-foreground" : "text-muted-foreground group-hover:text-foreground",
        )}
      />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

function Sidebar({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  const [toolsOpen, setToolsOpen] = useStoredFlag("swe-studio:tools-open", () => true);
  return (
    <div className="flex h-full flex-col">
      <Link
        href="/"
        onClick={onNavigate}
        className="flex h-[68px] shrink-0 items-center gap-2 px-6 md:h-[76px]"
      >
        <span className="orb h-5 w-5 rounded-full" />
        <span className="text-[18px] font-semibold tracking-[-0.4px]">SWE Studio</span>
      </Link>

      <nav className="flex-1 overflow-y-auto px-3.5 pb-4">
        <div className="flex flex-col gap-0.5">
          {PRIMARY.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} onNavigate={onNavigate} />
          ))}
        </div>

        <button
          type="button"
          onClick={() => setToolsOpen(!toolsOpen)}
          aria-expanded={toolsOpen}
          className="mt-6 flex h-8 w-full items-center justify-between rounded-lg px-2.5 text-[13px] font-medium text-muted-foreground transition-colors duration-200 ease-out-soft hover:text-foreground"
        >
          Tools
          <IconChevronDown
            className={cn(
              "size-3.5 transition-transform duration-300 ease-out-soft",
              !toolsOpen && "-rotate-90",
            )}
          />
        </button>
        {/* Height animates via the grid-rows 0fr -> 1fr trick: no JS measuring. */}
        <div
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-out-soft",
            toolsOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="overflow-hidden">
            <div className="ml-[19px] mt-0.5 flex flex-col gap-0.5 border-l border-border pl-2">
              {TOOLS.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        </div>
      </nav>

      <div className="flex flex-col gap-2 px-3.5 pb-4">
        <a
          href={`${REPO}#running-on-aws-eks--gpus`}
          target="_blank"
          rel="noreferrer"
          className="group rounded-2xl bg-background p-4 shadow-[0_1px_2px_rgba(0,0,0,0.05)] transition-[box-shadow,transform] duration-300 ease-out-soft hover:-translate-y-px hover:shadow-[0_6px_16px_-6px_rgba(0,0,0,0.12)]"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-foreground/70">
            <IconCloud className="size-[15px]" />
          </span>
          <p className="mt-2.5 text-[13px] font-medium">Run on Kubernetes</p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            Isolated agent Jobs on EKS, with GPU-served open models.
          </p>
        </a>
        <AuthorMenu />
      </div>
    </div>
  );
}

const pill =
  "inline-flex h-10 items-center gap-1.5 rounded-full bg-background px-4 text-sm font-medium shadow-[0_1px_2px_rgba(0,0,0,0.05)] transition-[box-shadow,transform] duration-200 ease-out-soft hover:shadow-[0_4px_12px_-4px_rgba(0,0,0,0.12)] active:scale-[0.97]";

const openPalette = () => window.dispatchEvent(new Event("swe-studio:open-palette"));

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  // Laptops and up start with the sidebar open; tablets start collapsed.
  const [sidebarOpen, setSidebarOpen] = useStoredFlag("swe-studio:sidebar", () => window.innerWidth >= 1024);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

  if (BARE.some((p) => pathname.startsWith(p))) return <>{children}</>;

  const toggle = () =>
    window.matchMedia("(min-width: 768px)").matches ? setSidebarOpen(!sidebarOpen) : setDrawer(true);

  return (
    <div className={cn("flex h-[100dvh] overflow-hidden", CANVAS)}>
      {/* Desktop sidebar: part of the canvas, no surface of its own. */}
      <aside
        className={cn(
          "hidden shrink-0 overflow-hidden transition-[width] duration-300 ease-out-soft md:block",
          sidebarOpen ? "w-[264px]" : "w-0",
        )}
      >
        <div
          className={cn(
            "h-full w-[264px] transition-opacity duration-200 ease-out-soft",
            sidebarOpen ? "opacity-100" : "opacity-0",
          )}
        >
          <Sidebar pathname={pathname} onNavigate={() => {}} />
        </div>
      </aside>

      {/* Mobile drawer: always mounted so it can slide both ways. */}
      <div
        className={cn("fixed inset-0 z-40 md:hidden", drawer ? "pointer-events-auto" : "pointer-events-none")}
        aria-hidden={!drawer}
      >
        <button
          type="button"
          tabIndex={drawer ? 0 : -1}
          aria-label="Close navigation"
          onClick={() => setDrawer(false)}
          className={cn(
            "absolute inset-0 bg-black/25 backdrop-blur-[2px] transition-opacity duration-300 ease-out-soft",
            drawer ? "opacity-100" : "opacity-0",
          )}
        />
        <aside
          className={cn(
            "absolute inset-y-0 left-0 w-[284px] max-w-[85vw] transition-[transform,box-shadow] duration-300 ease-out-soft",
            CANVAS,
            // Shadow only while open: off-screen, it would bleed in as a haze.
            drawer ? "translate-x-0 shadow-2xl" : "-translate-x-full shadow-none",
          )}
        >
          <Sidebar pathname={pathname} onNavigate={() => setDrawer(false)} />
        </aside>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[68px] shrink-0 items-center gap-2 px-2 md:h-[76px] md:gap-3 md:pl-1 md:pr-4">
          <button
            type="button"
            aria-label="Toggle navigation"
            onClick={toggle}
            className="rounded-full p-2.5 text-muted-foreground transition-[background-color,color,transform] duration-200 ease-out-soft hover:bg-foreground/[0.05] hover:text-foreground active:scale-95"
          >
            <IconPanel className="size-[18px]" />
          </button>

          <button
            type="button"
            onClick={openPalette}
            className="hidden h-11 w-full max-w-[460px] items-center gap-2.5 rounded-full bg-background px-4 text-[15px] text-muted-foreground shadow-[0_1px_2px_rgba(0,0,0,0.05)] transition-[box-shadow] duration-200 ease-out-soft hover:shadow-[0_4px_12px_-4px_rgba(0,0,0,0.12)] md:flex"
          >
            <IconSearch className="size-[18px]" />
            <span className="flex-1 truncate text-left">Search trajectories…</span>
            <kbd className="rounded-xl border border-border/70 px-1.5 py-px font-sans text-[11px]">⌘K</kbd>
          </button>

          <div className="flex flex-1 items-center justify-end gap-2">
            <button
              type="button"
              aria-label="Search"
              onClick={openPalette}
              className={cn(pill, "w-10 justify-center px-0 md:hidden")}
            >
              <IconSearch className="size-[18px]" />
            </button>
            <a href={`${REPO}/issues/new`} target="_blank" rel="noreferrer" className={cn(pill, "hidden lg:inline-flex")}>
              <IconMessage className="size-4 text-muted-foreground" />
              Feedback
            </a>
            <a href={REPO} target="_blank" rel="noreferrer" className={cn(pill, "hidden sm:inline-flex")}>
              <IconBook className="size-4 text-muted-foreground" />
              Docs
            </a>
            <UserMenu />
          </div>
        </header>

        {/* The sheet: an inset panel, rounded on every corner. */}
        <div
          className={cn(
            "mx-2 mb-2 flex min-h-0 flex-1 flex-col overflow-hidden rounded-[24px] border border-border/70 bg-background transition-[margin] duration-300 ease-out-soft md:mb-3 md:mr-3 md:rounded-[32px]",
            // With the sidebar collapsed the sheet keeps a canvas gutter on the left too.
            sidebarOpen ? "md:ml-0" : "md:ml-3",
          )}
        >
          <main className="flex-1 overflow-y-auto overscroll-contain">
            {/* Keyed on the route so each page eases in. */}
            <div key={pathname} className="page-enter mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
