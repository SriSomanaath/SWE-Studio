"use client";

import { useEffect, useState } from "react";

import { getAuthor, setAuthor } from "@/lib/author";
import { cn } from "@/lib/cn";

export function AuthorMenu() {
  const [name, setName] = useState("anonymous");
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    const stored = getAuthor();
    setName(stored);
    setDraft(stored);
  }, []);

  function save() {
    const next = setAuthor(draft);
    setName(next);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-sm",
          "transition-colors duration-200 ease-out-soft hover:bg-foreground/[0.045]",
        )}
        title="Set your display name (stored locally)"
      >
        <span className="h-5 w-5 shrink-0 rounded-md bg-gradient-to-br from-cyan-400 via-indigo-500 to-violet-500" />
        <span className="min-w-0 flex-1 truncate font-medium">{name}</span>
        <span className="text-[11px] text-muted-foreground">author</span>
      </button>
      {open && (
        <div className="pop-in absolute bottom-full left-0 z-30 mb-2 w-64 rounded-2xl border border-border bg-card p-3 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.2)] [--pop-origin:bottom_left]">
          <p className="text-xs font-medium text-muted-foreground">Your name</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Used on annotations and bookmarks. Stored in this browser only.
          </p>
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="ada"
            className="mt-2 w-full rounded-xl border border-border/70 bg-background px-2.5 py-1.5 text-sm outline-none focus:border-foreground/40"
            maxLength={64}
            onKeyDown={(e) => {
              if (e.key === "Enter") save();
              if (e.key === "Escape") setOpen(false);
            }}
          />
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-xl border border-border/70 px-2 py-1 text-xs hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              className="rounded-xl border border-border/70 bg-foreground px-2 py-1 text-xs text-background hover:opacity-90"
            >
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
