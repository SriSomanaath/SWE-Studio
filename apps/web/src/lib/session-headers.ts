"use client";

import { getSession } from "next-auth/react";

/**
 * Build the X-Studio-* identity headers from the current NextAuth session.
 * Used by `lib/client.ts` so every mutation carries the signed-in user's id,
 * name, and email to the API.
 */
export async function studioIdentityHeaders(): Promise<Record<string, string>> {
  try {
    const session = await getSession();
    if (!session?.user) return {};
    const headers: Record<string, string> = {};
    const userId = (session as { userId?: string }).userId;
    if (userId) headers["X-Studio-User"] = userId;
    if (session.user.name) headers["X-Studio-Name"] = session.user.name;
    if (session.user.email) headers["X-Studio-Email"] = session.user.email;
    return headers;
  } catch {
    return {};
  }
}
