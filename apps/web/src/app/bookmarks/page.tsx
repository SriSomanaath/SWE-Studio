import Link from "next/link";

import { Card, CardBody } from "@/components/Card";
import { listBookmarks } from "@/lib/api";

export const dynamic = "force-dynamic";

function formatTime(t: number): string {
  return new Date(t * 1000).toLocaleString();
}

export default async function BookmarksPage({
  searchParams,
}: {
  searchParams: Promise<{ author?: string }>;
}) {
  const { author } = await searchParams;
  let bookmarks: Awaited<ReturnType<typeof listBookmarks>> = [];
  let error: string | null = null;
  try {
    bookmarks = await listBookmarks(author);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load bookmarks";
    bookmarks = [];
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Bookmarks</h1>
        <p className="text-sm text-muted-foreground">
          {author ? (
            <>
              Showing bookmarks by <span className="font-mono">@{author}</span>.{" "}
              <Link href="/bookmarks" className="hover:text-foreground">
                Show all →
              </Link>
            </>
          ) : (
            "All bookmarks across authors. Star a trajectory to add one."
          )}
        </p>
      </div>

      {error && (
        <Card>
          <CardBody>
            <p className="text-sm text-[hsl(var(--danger))]">{error}</p>
          </CardBody>
        </Card>
      )}

      {bookmarks.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-muted-foreground">
              No bookmarks yet. Open a trajectory and click the ☆ to bookmark it.
            </p>
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/30 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="p-3">Run</th>
                  <th className="p-3">Trajectory</th>
                  <th className="p-3">By</th>
                  <th className="p-3">Note</th>
                  <th className="p-3 text-right">Added</th>
                </tr>
              </thead>
              <tbody>
                {bookmarks.map((b) => (
                  <tr
                    key={`${b.run_id}:${b.trajectory_id}:${b.author}`}
                    className="border-b border-border last:border-b-0 hover:bg-muted/30"
                  >
                    <td className="p-3 font-mono text-xs">
                      <Link href={`/runs/${b.run_id}`} className="hover:text-foreground">
                        {b.run_id}
                      </Link>
                    </td>
                    <td className="p-3">
                      <Link
                        href={`/runs/${b.run_id}/${b.trajectory_id}`}
                        className="font-mono text-xs hover:text-foreground"
                      >
                        {b.trajectory_id}
                      </Link>
                    </td>
                    <td className="p-3 font-mono text-xs text-muted-foreground">
                      <Link
                        href={`/bookmarks?author=${encodeURIComponent(b.author)}`}
                        className="hover:text-foreground"
                      >
                        @{b.author}
                      </Link>
                    </td>
                    <td className="p-3 text-xs">
                      {b.note || <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="p-3 text-right text-xs text-muted-foreground">
                      {formatTime(b.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
