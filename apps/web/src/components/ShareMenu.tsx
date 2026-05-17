"use client";

import { useState } from "react";

import { API_URL } from "@/lib/api";
import { createShare } from "@/lib/client";
import { cn } from "@/lib/cn";

const TTL_OPTIONS: Array<{ label: string; seconds: number | null }> = [
  { label: "1 hour", seconds: 3600 },
  { label: "1 day", seconds: 86400 },
  { label: "1 week", seconds: 604800 },
  { label: "Never expire", seconds: null },
];

export function ShareMenu({
  runId,
  trajectoryId,
}: {
  runId: string;
  trajectoryId: string;
}) {
  const [open, setOpen] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showTtl, setShowTtl] = useState(false);

  function show(msg: string) {
    setFlash(msg);
    window.setTimeout(() => setFlash(null), 1500);
  }

  async function copyMarkdown() {
    const res = await fetch(
      `${API_URL}/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/export.md`,
    );
    if (!res.ok) {
      show("Failed");
      return;
    }
    const text = await res.text();
    await navigator.clipboard.writeText(text);
    show("Copied Markdown");
  }

  async function copyLink() {
    if (typeof window === "undefined") return;
    await navigator.clipboard.writeText(window.location.href);
    show("Copied page link");
  }

  async function makePublicLink(ttlSeconds: number | null) {
    setBusy(true);
    try {
      const { url } = await createShare({
        kind: "trajectory",
        runId,
        trajectoryId,
        ttlSeconds,
      });
      await navigator.clipboard.writeText(url);
      show("Copied public link");
      setShowTtl(false);
      setOpen(false);
    } catch (err) {
      show(err instanceof Error ? err.message.slice(0, 40) : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const exportUrl = `${API_URL}/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/export.md`;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          setShowTtl(false);
        }}
        className="rounded-md border border-border px-2.5 py-1 text-xs hover:bg-accent"
      >
        Share ▾
      </button>
      {flash && (
        <span className="absolute -bottom-7 right-0 rounded-md border border-border bg-card px-2 py-1 text-[10px]">
          {flash}
        </span>
      )}
      {open && (
        <div className="absolute right-0 top-full z-20 mt-2 w-60 rounded-md border border-border bg-card p-2 shadow-lg">
          <MenuItem onClick={copyLink}>Copy page link</MenuItem>
          <MenuItem onClick={copyMarkdown}>Copy as Markdown</MenuItem>
          <a
            href={exportUrl}
            download={`${trajectoryId}.md`}
            onClick={() => setOpen(false)}
            className="block w-full rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent"
          >
            Download .md
          </a>

          <div className="my-1 border-t border-border" />

          {!showTtl ? (
            <MenuItem
              onClick={() => setShowTtl(true)}
              disabled={busy}
              accent
            >
              Create public link…
            </MenuItem>
          ) : (
            <div className="px-2 py-1.5 text-xs">
              <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                Expires in
              </p>
              <div className="flex flex-col gap-1">
                {TTL_OPTIONS.map((o) => (
                  <button
                    key={o.label}
                    type="button"
                    disabled={busy}
                    onClick={() => makePublicLink(o.seconds)}
                    className={cn(
                      "rounded-md border border-border px-2 py-1 text-left text-xs",
                      busy ? "opacity-50" : "hover:bg-accent",
                    )}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MenuItem({
  onClick,
  children,
  disabled,
  accent,
}: {
  onClick: () => void;
  children: React.ReactNode;
  disabled?: boolean;
  accent?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "block w-full rounded-md px-2 py-1.5 text-left text-xs",
        disabled && "opacity-50",
        !disabled && "hover:bg-accent",
        accent && "text-[hsl(var(--success))]",
      )}
    >
      {children}
    </button>
  );
}
