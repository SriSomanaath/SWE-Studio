"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { searchTrajectories } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { SearchHit } from "@/lib/types";

import { buildHref } from "./SearchHits";

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const fetchAbort = useRef<AbortController | null>(null);
  const debounceTimer = useRef<number | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    }
    // The header search box opens the palette without simulating a keypress.
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("swe-studio:open-palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("swe-studio:open-palette", onOpen);
    };
  }, [open]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setQuery("");
      setHits([]);
      setActive(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (debounceTimer.current != null) window.clearTimeout(debounceTimer.current);
    if (!query.trim()) {
      setHits([]);
      return;
    }
    debounceTimer.current = window.setTimeout(async () => {
      fetchAbort.current?.abort();
      const ctrl = new AbortController();
      fetchAbort.current = ctrl;
      setBusy(true);
      try {
        const res = await searchTrajectories({ q: query, limit: 12 });
        if (!ctrl.signal.aborted) {
          setHits(res.hits);
          setActive(0);
        }
      } catch {
        // silent
      } finally {
        setBusy(false);
      }
    }, 200);
  }, [query, open]);

  function go(hit: SearchHit) {
    setOpen(false);
    router.push(buildHref(hit));
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-foreground/30 backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="mt-24 w-full max-w-xl overflow-hidden rounded-2xl border border-border/70 bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center border-b border-border px-3">
          <span className="text-xs text-muted-foreground">⌘K</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, Math.max(0, hits.length - 1)));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(0, a - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                if (hits[active]) {
                  go(hits[active]);
                } else if (query.trim()) {
                  setOpen(false);
                  router.push(`/search?q=${encodeURIComponent(query)}`);
                }
              }
            }}
            placeholder="Search trajectories, steps, annotations…"
            className="w-full bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted-foreground"
          />
          {busy && (
            <span className="mr-2 text-[10px] font-medium text-muted-foreground">
              searching
            </span>
          )}
        </div>

        <ul className="max-h-[60vh] overflow-y-auto">
          {hits.length === 0 && query.trim() && !busy && (
            <li className="px-4 py-6 text-center text-sm text-muted-foreground">No hits.</li>
          )}
          {hits.length === 0 && !query.trim() && (
            <li className="px-4 py-6 text-center text-sm text-muted-foreground">
              Type to search. ↑/↓ to navigate, ↵ to open, Esc to close.
            </li>
          )}
          {hits.map((hit, i) => (
            <li key={`${hit.kind}-${hit.run_id}:${hit.trajectory_id}-${i}`}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onClick={() => go(hit)}
                className={cn(
                  "block w-full border-b border-border px-3 py-2 text-left last:border-b-0",
                  i === active ? "bg-accent" : "hover:bg-accent/50",
                )}
              >
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-medium font-medium",
                      hit.kind === "trajectory"
                        ? "bg-muted text-muted-foreground"
                        : "bg-[hsl(var(--warning))]/15 text-[hsl(var(--warning))]",
                    )}
                  >
                    {hit.kind}
                  </span>
                  <span className="truncate font-mono">
                    {hit.run_id} · {hit.trajectory_id}
                    {hit.step_index != null && ` · step ${hit.step_index + 1}`}
                  </span>
                </div>
                <p
                  className="mt-1 line-clamp-2 text-xs text-muted-foreground"
                  dangerouslySetInnerHTML={{ __html: renderSnippet(hit.snippet) }}
                />
              </button>
            </li>
          ))}
        </ul>

        {query.trim() && (
          <div className="border-t border-border bg-muted/30 px-3 py-2 text-[10px] font-medium text-muted-foreground">
            ↵ jump · ↑↓ navigate · Esc close
          </div>
        )}
      </div>
    </div>
  );
}

function renderSnippet(s: string): string {
  const escaped = s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped.replace(
    /\[([^\]]+)\]/g,
    '<mark class="rounded bg-[hsl(var(--warning))]/30 px-0.5 text-foreground">$1</mark>',
  );
}
