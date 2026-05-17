import type { EvalStatus } from "@/lib/types";

import { Badge } from "./Badge";

export function EvalPill({ status }: { status: EvalStatus }) {
  if (status.resolved == null && status.submitted == null && status.completed == null) {
    return <Badge variant="outline">unscored</Badge>;
  }
  if (status.resolved) return <Badge variant="success">resolved</Badge>;
  if (status.submitted) return <Badge variant="warning">submitted</Badge>;
  if (status.completed) return <Badge variant="warning">completed</Badge>;
  return <Badge variant="danger">failed</Badge>;
}
