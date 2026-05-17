"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { getAuthor } from "@/lib/author";
import { putBookmark, removeBookmark } from "@/lib/client";
import { cn } from "@/lib/cn";

export function BookmarkButton({
  runId,
  trajectoryId,
  initialIsBookmarked,
}: {
  runId: string;
  trajectoryId: string;
  initialIsBookmarked: boolean;
}) {
  const router = useRouter();
  const [active, setActive] = useState(initialIsBookmarked);
  const [, startTransition] = useTransition();
  const [busy, setBusy] = useState(false);
  const [me, setMe] = useState("anonymous");

  useEffect(() => setMe(getAuthor()), []);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    try {
      if (active) {
        await removeBookmark(runId, trajectoryId);
        setActive(false);
      } else {
        await putBookmark(runId, trajectoryId);
        setActive(true);
      }
      startTransition(() => router.refresh());
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      title={active ? `Bookmarked as @${me}` : "Bookmark this trajectory"}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs",
        active ? "bg-[hsl(var(--warning))]/15 text-[hsl(var(--warning))]" : "hover:bg-accent",
      )}
    >
      <span aria-hidden>{active ? "★" : "☆"}</span>
      <span>{active ? "Bookmarked" : "Bookmark"}</span>
    </button>
  );
}
