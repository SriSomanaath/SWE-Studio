import { Card, CardBody } from "@/components/Card";
import { Stat } from "@/components/Stat";
import { cn } from "@/lib/cn";
import type { DiffAnalysis } from "@/lib/types";

export function DiffOverlapPanel({ analysis }: { analysis: DiffAnalysis | null | undefined }) {
  if (!analysis) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-muted-foreground">
            Neither trajectory submitted a patch; no diff overlap to compute.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <h2 className="text-sm font-semibold">Patch overlap</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Files touched by each trajectory&apos;s final submission and where they agree.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-5">
          <Stat label="Files in both" value={analysis.files_in_both} />
          <Stat label="Only A" value={analysis.files_only_a} />
          <Stat label="Only B" value={analysis.files_only_b} />
          <Stat label="A · total" value={analysis.files_a_count} />
          <Stat label="B · total" value={analysis.files_b_count} />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          File overlap (Jaccard):{" "}
          <span className="font-mono text-foreground">
            {(analysis.file_overlap_ratio * 100).toFixed(0)}%
          </span>
        </p>

        {analysis.files.length > 0 && (
          <div className="mt-4 overflow-hidden rounded-xl border border-border/70">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/30 text-left text-xs font-medium text-muted-foreground">
                <tr>
                  <th className="p-2.5">File</th>
                  <th className="p-2.5">Side</th>
                  <th className="p-2.5 text-right">+A / −A</th>
                  <th className="p-2.5 text-right">+B / −B</th>
                </tr>
              </thead>
              <tbody>
                {analysis.files.map((f) => {
                  const both = f.in_a && f.in_b;
                  return (
                    <tr
                      key={f.path}
                      className={cn(
                        "border-b border-border last:border-b-0",
                        both && "bg-[hsl(var(--success))]/5",
                      )}
                    >
                      <td className="p-2.5 font-mono text-xs">{f.path}</td>
                      <td className="p-2.5">
                        <span className="flex gap-1 font-mono text-[10px] font-medium">
                          <Pill on={f.in_a}>A</Pill>
                          <Pill on={f.in_b}>B</Pill>
                        </span>
                      </td>
                      <td className="p-2.5 text-right font-mono text-xs">
                        {f.in_a ? (
                          <>
                            <span className="text-[hsl(var(--success))]">+{f.added_a}</span>
                            <span className="text-muted-foreground"> / </span>
                            <span className="text-[hsl(var(--danger))]">−{f.removed_a}</span>
                          </>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="p-2.5 text-right font-mono text-xs">
                        {f.in_b ? (
                          <>
                            <span className="text-[hsl(var(--success))]">+{f.added_b}</span>
                            <span className="text-muted-foreground"> / </span>
                            <span className="text-[hsl(var(--danger))]">−{f.removed_b}</span>
                          </>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function Pill({ on, children }: { on: boolean; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5",
        on
          ? "bg-foreground text-background"
          : "border border-border text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}
