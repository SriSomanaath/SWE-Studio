import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="text-sm text-muted-foreground">
        That run or trajectory does not exist in the configured directory.
      </p>
      <Link
        href="/"
        className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
      >
        Back to runs
      </Link>
    </div>
  );
}
