"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { useState } from "react";

import { cn } from "@/lib/cn";

export function UserMenu() {
  const { data: session, status } = useSession();
  const [open, setOpen] = useState(false);

  if (status === "loading") {
    return (
      <span className="rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground">
        …
      </span>
    );
  }

  if (status === "unauthenticated" || !session?.user) {
    return (
      <Link
        href="/login"
        className="rounded-md border border-border px-2.5 py-1 text-xs hover:bg-accent"
      >
        Sign in
      </Link>
    );
  }

  const name = session.user.name || session.user.email || "User";

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "rounded-md border border-border px-2.5 py-1 text-xs",
          "hover:bg-accent",
        )}
        title="Account menu"
      >
        @{name}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-2 w-48 rounded-md border border-border bg-card p-2 shadow-lg">
          <div className="px-2 py-1 text-[10px] text-muted-foreground">
            {session.user.email ?? ""}
          </div>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/" })}
            className="block w-full rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
