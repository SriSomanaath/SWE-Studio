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
          "rounded-md border border-border px-2.5 py-1 text-xs",
          "hover:bg-accent",
        )}
        title="Set your display name (stored locally)"
      >
        @{name}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-2 w-64 rounded-md border border-border bg-card p-3 shadow-lg">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Your name</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Used on annotations and bookmarks. Stored in this browser only.
          </p>
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="ada"
            className="mt-2 w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-foreground/40"
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
              className="rounded-md border border-border px-2 py-1 text-xs hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              className="rounded-md border border-border bg-foreground px-2 py-1 text-xs text-background hover:opacity-90"
            >
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
