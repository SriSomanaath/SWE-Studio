import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AppShell } from "@/components/AppShell";
import { AuthProviders } from "@/components/AuthProviders";
import { CommandPalette } from "@/components/CommandPalette";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

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
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body>
        <AuthProviders>
          <AppShell>{children}</AppShell>
          <CommandPalette />
        </AuthProviders>
      </body>
    </html>
  );
}
