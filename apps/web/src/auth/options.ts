/**
 * NextAuth v4 configuration.
 *
 * Two providers:
 *   - GitHub OAuth, used when `AUTH_GITHUB_ID` + `AUTH_GITHUB_SECRET` are set.
 *     Register an OAuth app at https://github.com/settings/developers; the
 *     callback URL should be `${NEXTAUTH_URL}/api/auth/callback/github`.
 *   - "dev" Credentials provider, used when `AUTH_DEV_CREDENTIALS=true`.
 *     Accepts any non-empty username and creates a stable per-name id.
 *     Convenient for local development.
 *
 * On a successful sign-in we stamp the user's id, name, and email onto the
 * JWT (and thus the session) so the rest of the app can read them without
 * another round-trip.
 */

import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GitHubProvider from "next-auth/providers/github";

const providers: NextAuthOptions["providers"] = [];

if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) {
  providers.push(
    GitHubProvider({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
    }),
  );
}

if (process.env.AUTH_DEV_CREDENTIALS !== "false") {
  providers.push(
    CredentialsProvider({
      id: "dev",
      name: "Dev login",
      credentials: {
        username: { label: "Username", type: "text" },
      },
      async authorize(creds) {
        const username = (creds?.username ?? "").trim();
        if (!username) return null;
        return {
          id: `dev:${username.toLowerCase()}`,
          name: username,
          email: `${username.toLowerCase()}@studio.local`,
        };
      },
    }),
  );
}

export const authOptions: NextAuthOptions = {
  providers,
  session: { strategy: "jwt" },
  secret:
    process.env.AUTH_SECRET ??
    process.env.NEXTAUTH_SECRET ??
    "dev-secret-do-not-use-in-production",
  pages: { signIn: "/login" },
  callbacks: {
    async jwt({ token, user, account }) {
      if (user) {
        const provider = account?.provider ?? "dev";
        const baseId = user.id ?? user.email ?? user.name;
        // Normalize the subject so the API sees a stable `provider:something`.
        if (baseId && !String(baseId).includes(":")) {
          token.sub = `${provider}:${baseId}`;
        }
        if (user.name) token.name = user.name;
        if (user.email) token.email = user.email;
      }
      return token;
    },
    async session({ session, token }) {
      if (token?.sub) (session as { userId?: string }).userId = token.sub;
      return session;
    },
  },
};
