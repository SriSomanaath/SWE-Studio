import { cn } from "@/lib/cn";

// Number first, label second: the value is what people scan for.
export function Stat({
  label,
  value,
  className,
  tile = false,
}: {
  label: string;
  value: React.ReactNode;
  className?: string;
  /** Render as its own KPI tile (soft filled surface). */
  tile?: boolean;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", tile && "kpi-tile", className)}>
      <span className="truncate text-[22px] font-semibold leading-none tracking-[-0.5px] tabular-nums">
        {value}
      </span>
      <span className="truncate text-[13px] text-muted-foreground">{label}</span>
    </div>
  );
}
