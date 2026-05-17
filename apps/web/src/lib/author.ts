"use client";

const KEY = "swe-studio:author";

export function getAuthor(): string {
  if (typeof window === "undefined") return "anonymous";
  return window.localStorage.getItem(KEY) || "anonymous";
}

export function setAuthor(name: string): string {
  const clean = name.trim().slice(0, 64) || "anonymous";
  if (typeof window !== "undefined") {
    window.localStorage.setItem(KEY, clean);
  }
  return clean;
}
