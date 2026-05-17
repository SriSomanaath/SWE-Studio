import { cn } from "@/lib/cn";

export function CodeBlock({
  children,
  className,
  language,
}: {
  children: string;
  className?: string;
  language?: string;
}) {
  if (!children) {
    return <div className="text-sm text-muted-foreground italic">empty</div>;
  }
  return (
    <pre
      className={cn(
        "max-h-[400px] overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed",
        className,
      )}
      data-language={language}
    >
      <code>{children}</code>
    </pre>
  );
}
