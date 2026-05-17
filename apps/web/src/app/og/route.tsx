import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

export const runtime = "edge";

const KIND_COLORS: Record<string, { label: string; accent: string }> = {
  trajectory: { label: "Trajectory", accent: "#22c55e" },
  run: { label: "Run", accent: "#a3a3a3" },
  showcase: { label: "Showcase", accent: "#f59e0b" },
  integration: { label: "Integration", accent: "#3b82f6" },
  analytics: { label: "Analytics", accent: "#8b5cf6" },
  compare: { label: "Compare", accent: "#ec4899" },
};

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const title = (params.get("title") || "SWE Studio").slice(0, 120);
  const subtitle = (params.get("subtitle") || "").slice(0, 200);
  const kindRaw = params.get("kind") || "trajectory";
  const kind = KIND_COLORS[kindRaw] ?? KIND_COLORS.trajectory;

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          background: "linear-gradient(135deg, #0a0a0c 0%, #18181b 100%)",
          color: "#fafafa",
          padding: 64,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: 3,
              background: "#22c55e",
            }}
          />
          <span style={{ fontSize: 28, fontWeight: 600 }}>SWE Studio</span>
        </div>

        <div
          style={{
            marginTop: 36,
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 14,
              padding: "4px 10px",
              borderRadius: 6,
              background: kind.accent,
              color: "#0a0a0c",
              textTransform: "uppercase",
              letterSpacing: 1.5,
              fontWeight: 600,
            }}
          >
            {kind.label}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginTop: 24,
            gap: 18,
            flex: 1,
            justifyContent: "center",
          }}
        >
          <h1
            style={{
              fontSize: 64,
              lineHeight: 1.05,
              fontWeight: 600,
              margin: 0,
              letterSpacing: -1,
              fontFamily: "ui-monospace, SFMono-Regular, monospace",
            }}
          >
            {title}
          </h1>
          {subtitle && (
            <p
              style={{
                fontSize: 28,
                color: "#a1a1aa",
                margin: 0,
                lineHeight: 1.3,
              }}
            >
              {subtitle}
            </p>
          )}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 18,
            color: "#71717a",
            marginTop: 32,
          }}
        >
          <span>Observability for coding agents</span>
          <span style={{ fontFamily: "ui-monospace, monospace" }}>swe-studio</span>
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
