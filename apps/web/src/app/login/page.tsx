"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";

import { cn } from "@/lib/cn";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState<null | "github" | "dev">(null);

  async function signInWithGithub() {
    setBusy("github");
    try {
      await signIn("github", { callbackUrl: "/" });
    } finally {
      setBusy(null);
    }
  }

  async function signInWithDev() {
    if (!username.trim()) return;
    setBusy("dev");
    try {
      await signIn("dev", { username, callbackUrl: "/" });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold">Sign in to SWE Studio</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a sign-in method to access workspaces and shared annotations.
        </p>
      </div>

      <button
        type="button"
        onClick={signInWithGithub}
        disabled={busy != null}
        className={cn(
          "rounded-md border border-border bg-foreground px-3 py-2 text-sm text-background",
          "hover:opacity-90 disabled:opacity-50",
        )}
      >
        {busy === "github" ? "Redirecting…" : "Continue with GitHub"}
      </button>
      <p className="text-xs text-muted-foreground">
        GitHub sign-in needs <code className="font-mono">AUTH_GITHUB_ID</code> +{" "}
        <code className="font-mono">AUTH_GITHUB_SECRET</code> in{" "}
        <code className="font-mono">.env.local</code>.{" "}
        <a
          className="underline hover:text-foreground"
          href="https://github.com/settings/developers"
          target="_blank"
          rel="noreferrer"
        >
          Register an OAuth app
        </a>{" "}
        and set callback{" "}
        <code className="font-mono">/api/auth/callback/github</code>.
      </p>

      <div className="flex items-center gap-3 text-xs uppercase tracking-wide text-muted-foreground">
        <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void signInWithDev();
        }}
        className="flex flex-col gap-2"
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="uppercase tracking-wide text-muted-foreground">
            Dev login (local only)
          </span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="ada"
            className="rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-foreground/40"
            autoComplete="off"
          />
        </label>
        <button
          type="submit"
          disabled={!username.trim() || busy != null}
          className={cn(
            "rounded-md border border-border px-3 py-2 text-sm",
            "hover:bg-accent disabled:opacity-50",
          )}
        >
          {busy === "dev" ? "Signing in…" : "Continue with a username"}
        </button>
        <p className="text-[10px] text-muted-foreground">
          Accepts any non-empty username. Disable with{" "}
          <code className="font-mono">AUTH_DEV_CREDENTIALS=false</code>.
        </p>
      </form>
    </div>
  );
}
