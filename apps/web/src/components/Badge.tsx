import { cn } from "@/lib/cn";

type Variant = "default" | "success" | "danger" | "warning" | "outline";

const variantStyles: Record<Variant, string> = {
  default: "bg-muted text-foreground",
  success: "bg-[hsl(var(--success))]/15 text-[hsl(var(--success))]",
  danger: "bg-[hsl(var(--danger))]/15 text-[hsl(var(--danger))]",
  warning: "bg-[hsl(var(--warning))]/15 text-[hsl(var(--warning))]",
  outline: "border border-border text-muted-foreground",
};

export function Badge({
  variant = "default",
  className,
  children,
}: {
  variant?: Variant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
