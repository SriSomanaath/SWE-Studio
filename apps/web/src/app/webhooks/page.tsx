import type { Metadata } from "next";

import { Card, CardBody } from "@/components/Card";
import { WebhookManager } from "@/components/WebhookManager";
import { listWebhooks } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Webhooks · SWE Studio",
  description:
    "Subscribe a URL to SWE Studio events — trajectory completions, resolutions, summaries, bookmarks — and forward them to Slack, Discord, or your CI pipeline.",
  alternates: { canonical: "/webhooks" },
};

export default async function WebhooksPage() {
  let hooks: Awaited<ReturnType<typeof listWebhooks>> = [];
  let error: string | null = null;
  try {
    hooks = await listWebhooks();
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load webhooks";
    hooks = [];
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Webhooks</h1>
        <p className="text-sm text-muted-foreground">
          Forward Studio events to any HTTPS endpoint. Each delivery is signed with HMAC-SHA256 so
          your receiver can verify authenticity. Failed deliveries are retried with exponential
          backoff and recorded in the deliveries table for visibility.
        </p>
      </div>

      {error && (
        <Card>
          <CardBody>
            <p className="text-sm text-[hsl(var(--danger))]">{error}</p>
          </CardBody>
        </Card>
      )}

      <WebhookManager initial={hooks} />

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold">Verifying a delivery</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Every POST carries an{" "}
            <code className="font-mono">X-Studio-Signature</code> header of the form{" "}
            <code className="font-mono">sha256=&lt;hex&gt;</code>. Recompute the HMAC over the raw
            request body and compare:
          </p>
          <pre className="mt-3 overflow-auto rounded-xl border border-border/70 bg-muted/40 p-3 font-mono text-xs">
{`# Python (FastAPI receiver):
import hmac, hashlib
def verify(secret: str, body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)

# Node:
import { createHmac, timingSafeEqual } from "node:crypto";
function verify(secret, body, header) {
  const expected = "sha256=" + createHmac("sha256", secret).update(body).digest("hex");
  return timingSafeEqual(Buffer.from(expected), Buffer.from(header));
}`}
          </pre>
        </CardBody>
      </Card>
    </div>
  );
}
