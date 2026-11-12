"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";

import { cn } from "@/lib/cn";
import {
  DEFAULT_FILTERS,
  SortField,
  SortOrder,
  StatusFilter,
  TrajectoryFilters,
} from "@/lib/types";

const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: "any", label: "Any" },
  { value: "resolved", label: "Resolved" },
  { value: "submitted", label: "Submitted" },
  { value: "failed", label: "Failed" },
  { value: "unscored", label: "Unscored" },
];

const SORT_OPTIONS: Array<{ value: SortField; label: string }> = [
  { value: "id", label: "Instance ID" },
  { value: "instance_cost", label: "Cost" },
  { value: "api_calls", label: "API calls" },
  { value: "step_count", label: "Steps" },
  { value: "tokens_sent", label: "Tokens in" },
];

function readFilters(params: URLSearchParams): TrajectoryFilters {
  return {
    status: (params.get("status") as StatusFilter) || DEFAULT_FILTERS.status,
    exit: params.get("exit") ?? "",
    search: params.get("search") ?? "",
    costMin: params.get("cost_min") ?? "",
    costMax: params.get("cost_max") ?? "",
    sort: (params.get("sort") as SortField) || DEFAULT_FILTERS.sort,
    order: (params.get("order") as SortOrder) || DEFAULT_FILTERS.order,
  };
}

function toQuery(filters: TrajectoryFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.status !== "any") params.set("status", filters.status);
  if (filters.exit) params.set("exit", filters.exit);
  if (filters.search) params.set("search", filters.search);
  if (filters.costMin) params.set("cost_min", filters.costMin);
  if (filters.costMax) params.set("cost_max", filters.costMax);
  if (filters.sort !== "id") params.set("sort", filters.sort);
  if (filters.order !== "asc") params.set("order", filters.order);
  return params;
}

export function FiltersBar({ total }: { total: number }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const urlFilters = useMemo(() => readFilters(searchParams), [searchParams]);
  const [filters, setFilters] = useState<TrajectoryFilters>(urlFilters);
  const [, startTransition] = useTransition();
  const debounceRef = useRef<number | null>(null);

  // Stay in sync if the URL changes externally (back/forward).
  useEffect(() => {
    setFilters(urlFilters);
  }, [urlFilters]);

  function push(next: TrajectoryFilters, debounceMs = 0) {
    const apply = () => {
      const qs = toQuery(next).toString();
      startTransition(() => {
        router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
      });
    };
    if (debounceMs <= 0) {
      apply();
      return;
    }
    if (debounceRef.current != null) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(apply, debounceMs);
  }

  function update<K extends keyof TrajectoryFilters>(
    key: K,
    value: TrajectoryFilters[K],
    debounceMs = 0,
  ) {
    const next = { ...filters, [key]: value };
    setFilters(next);
    push(next, debounceMs);
  }

  function reset() {
    setFilters(DEFAULT_FILTERS);
    startTransition(() => {
      router.replace(pathname, { scroll: false });
    });
  }

  const hasActiveFilters =
    filters.status !== "any" ||
    filters.exit !== "" ||
    filters.search !== "" ||
    filters.costMin !== "" ||
    filters.costMax !== "" ||
    filters.sort !== "id" ||
    filters.order !== "asc";

  return (
    <div className="surface-soft flex flex-col gap-3 p-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_auto_auto_auto_auto] md:items-end">
        <FilterField label="Search">
          <input
            type="search"
            value={filters.search}
            onChange={(e) => update("search", e.target.value, 300)}
            placeholder="instance id or problem text…"
            className="w-full rounded-xl border border-border/70 bg-background px-2.5 py-1.5 text-sm outline-none ring-0 focus:border-foreground/40"
          />
        </FilterField>

        <FilterField label="Status">
          <Select
            value={filters.status}
            onChange={(v) => update("status", v as StatusFilter)}
            options={STATUS_OPTIONS}
          />
        </FilterField>

        <FilterField label="Exit contains">
          <input
            type="text"
            value={filters.exit}
            onChange={(e) => update("exit", e.target.value, 300)}
            placeholder="submitted, forfeit…"
            className="w-36 rounded-xl border border-border/70 bg-background px-2.5 py-1.5 font-mono text-xs outline-none focus:border-foreground/40"
          />
        </FilterField>

        <FilterField label="Cost ≥">
          <input
            type="number"
            inputMode="decimal"
            min={0}
            step={0.01}
            value={filters.costMin}
            onChange={(e) => update("costMin", e.target.value, 300)}
            placeholder="0"
            className="w-20 rounded-xl border border-border/70 bg-background px-2.5 py-1.5 text-right font-mono text-xs outline-none focus:border-foreground/40"
          />
        </FilterField>

        <FilterField label="Cost ≤">
          <input
            type="number"
            inputMode="decimal"
            min={0}
            step={0.01}
            value={filters.costMax}
            onChange={(e) => update("costMax", e.target.value, 300)}
            placeholder="∞"
            className="w-20 rounded-xl border border-border/70 bg-background px-2.5 py-1.5 text-right font-mono text-xs outline-none focus:border-foreground/40"
          />
        </FilterField>

        <FilterField label="Sort">
          <div className="flex items-stretch overflow-hidden rounded-xl border border-border/70">
            <Select
              value={filters.sort}
              onChange={(v) => update("sort", v as SortField)}
              options={SORT_OPTIONS}
              className="border-0 border-r border-border rounded-none"
            />
            <button
              type="button"
              onClick={() =>
                update("order", filters.order === "asc" ? "desc" : "asc")
              }
              className={cn(
                "px-2 text-xs font-medium hover:bg-accent",
                "bg-background",
              )}
              aria-label="Toggle sort order"
              title="Toggle ascending / descending"
            >
              {filters.order === "asc" ? "↑" : "↓"}
            </button>
          </div>
        </FilterField>
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Showing <span className="font-mono text-foreground">{total}</span>{" "}
          trajector{total === 1 ? "y" : "ies"}
        </span>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={reset}
            className="rounded-xl border border-border/70 px-2 py-1 hover:bg-accent"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function Select<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: Array<{ value: T; label: string }>;
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className={cn(
        "rounded-xl border border-border/70 bg-background px-2 py-1.5 text-sm outline-none focus:border-foreground/40",
        className,
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
