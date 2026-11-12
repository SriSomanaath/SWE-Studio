"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { useState } from "react";

import { cn } from "@/lib/cn";

export function UserMenu() {
  const { data: session, status } = useSession();
  const [open, setOpen] = useState(false);

  if (status === "loading") {
    return <span className="h-9 w-9 animate-pulse rounded-full bg-accent" />;
  }

  if (status === "unauthenticated" || !session?.user) {
    return (
      <Link
        href="/login"
        className="inline-flex h-10 items-center rounded-full bg-foreground px-4 text-sm font-medium text-background transition-[opacity,transform] duration-200 ease-out-soft hover:opacity-90 active:scale-[0.97]"
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
          "flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border border-border",
          "bg-gradient-to-br from-cyan-400 via-indigo-500 to-violet-500 text-sm font-semibold text-white",
          "ring-offset-2 ring-offset-background transition-[box-shadow,transform] duration-200 ease-out-soft hover:ring-2 hover:ring-border active:scale-95",
        )}
        title={name}
      >
        {session.user.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={session.user.image} alt="" className="h-full w-full object-cover" />
        ) : (
          name.slice(0, 1).toUpperCase()
        )}
      </button>
      {open && (
        <div className="pop-in absolute right-0 top-full z-30 mt-2 w-56 rounded-2xl border border-border bg-card p-1.5 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.2)]">
          <div className="px-2.5 py-2">
            <p className="truncate text-sm font-medium">{name}</p>
            <p className="truncate text-xs text-muted-foreground">{session.user.email ?? ""}</p>
          </div>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/" })}
            className="block w-full rounded-lg px-2.5 py-2 text-left text-sm hover:bg-accent"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
