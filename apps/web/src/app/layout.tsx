import type { Metadata } from "next";
import Link from "next/link";

import { AuthProviders } from "@/components/AuthProviders";
import { AuthorMenu } from "@/components/AuthorMenu";
import { CommandPalette } from "@/components/CommandPalette";
import { UserMenu } from "@/components/UserMenu";

import "./globals.css";

const siteUrl = process.env.SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "SWE Studio — Observability for coding agents",
    template: "%s · SWE Studio",
  },
  description:
    "Open-source viewer, observability and replay tool for coding agents. Step through agent trajectories, watch live runs, compare benchmarks, and analyze cost & pass-rate distributions.",
  keywords: [
    "SWE Studio",
    "coding agent observability",
    "agent trajectory viewer",
    "LLM agent dashboard",
    "agent replay",
    "agent benchmark",
  ],
  openGraph: {
    title: "SWE Studio — Observability for coding agents",
    description:
      "Step through agent trajectories, watch live runs, compare benchmarks, and analyze cost & pass-rate distributions.",
    url: siteUrl,
    siteName: "SWE Studio",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "SWE Studio",
    description: "Observability and replay for coding agents.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen">
        <AuthProviders>
        <div className="flex min-h-screen flex-col">
          <header className="border-b border-border bg-background/80 backdrop-blur">
            <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
              <Link href="/" className="flex items-center gap-2 font-semibold">
                <span className="inline-block h-2 w-2 rounded-sm bg-[hsl(var(--success))]" />
                SWE Studio
              </Link>
              <nav className="flex items-center gap-4 text-sm text-muted-foreground">
                <Link className="hover:text-foreground" href="/">
                  Runs
                </Link>
                <Link className="hover:text-foreground" href="/live">
                  Live
                </Link>
                <Link className="hover:text-foreground" href="/compare">
                  Compare
                </Link>
                <Link className="hover:text-foreground" href="/datasets">
                  Datasets
                </Link>
                <Link
                  className="rounded-md border border-border bg-foreground px-2.5 py-1 text-background hover:opacity-90"
                  href="/agent/new"
                >
                  Run agent →
                </Link>
                <Link className="hover:text-foreground" href="/showcase">
                  Showcase
                </Link>
                <Link className="hover:text-foreground" href="/integrations">
                  Integrations
                </Link>
                <Link className="hover:text-foreground" href="/search">
                  Search
                </Link>
                <Link className="hover:text-foreground" href="/bookmarks">
                  Bookmarks
                </Link>
                <Link className="hover:text-foreground" href="/webhooks">
                  Webhooks
                </Link>
                <AuthorMenu />
                <UserMenu />
              </nav>
            </div>
          </header>
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8">{children}</main>
          <CommandPalette />
          <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
            SWE Studio · Phase 13 · Workspaces, NextAuth, replay, presence
          </footer>
        </div>
        </AuthProviders>
      </body>
    </html>
  );
}
