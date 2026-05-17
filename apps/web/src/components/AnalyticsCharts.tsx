"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BucketPassRate, ExitStatusBreakdown, HistogramBin } from "@/lib/types";

const successColor = "hsl(142 71% 45%)";
const dangerColor = "hsl(0 84% 60%)";
const neutralColor = "hsl(240 5% 65%)";

const tooltipStyle: React.CSSProperties = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  fontSize: 12,
  fontFamily: "var(--font-sans, system-ui)",
};

export function CostHistogramChart({ bins }: { bins: HistogramBin[] }) {
  return (
    <ChartCard title="Cost distribution" subtitle="trajectories per cost bucket">
      <BarChart data={bins} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="label" tick={tickStyle} axisLine={axisStyle} tickLine={false} />
        <YAxis allowDecimals={false} tick={tickStyle} axisLine={axisStyle} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))" }} />
        <Bar dataKey="count" fill={successColor} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartCard>
  );
}

export function StepHistogramChart({ bins }: { bins: HistogramBin[] }) {
  return (
    <ChartCard title="Step-count distribution" subtitle="trajectories per step bucket">
      <BarChart data={bins} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="label" tick={tickStyle} axisLine={axisStyle} tickLine={false} />
        <YAxis allowDecimals={false} tick={tickStyle} axisLine={axisStyle} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))" }} />
        <Bar dataKey="count" fill={neutralColor} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartCard>
  );
}

export function PassRateChart({ buckets }: { buckets: BucketPassRate[] }) {
  const data = buckets.map((b) => ({
    label: b.label,
    rate: b.rate == null ? null : Math.round(b.rate * 1000) / 10,
    total: b.total,
    resolved: b.resolved,
  }));
  return (
    <ChartCard title="Pass rate by step bucket" subtitle="resolved / total (%)">
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="label" tick={tickStyle} axisLine={axisStyle} tickLine={false} />
        <YAxis
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
          tick={tickStyle}
          axisLine={axisStyle}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
        <Line
          type="monotone"
          dataKey="rate"
          stroke={successColor}
          strokeWidth={2}
          dot={{ r: 3, fill: successColor }}
          activeDot={{ r: 5 }}
          connectNulls
        />
      </LineChart>
    </ChartCard>
  );
}

export function ExitStatusChart({ data }: { data: ExitStatusBreakdown[] }) {
  const chartData = data.map((d) => ({
    exit: d.exit_status,
    resolved: d.resolved,
    other: Math.max(0, d.total - d.resolved),
  }));
  return (
    <ChartCard title="Exit status × eval" subtitle="resolved vs other per exit status">
      <BarChart
        data={chartData}
        margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
        stackOffset="expand"
      >
        <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="exit" tick={tickStyle} axisLine={axisStyle} tickLine={false} />
        <YAxis allowDecimals={false} tick={tickStyle} axisLine={axisStyle} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))" }} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "hsl(var(--muted-foreground))" }}
          iconType="circle"
        />
        <Bar dataKey="resolved" stackId="a" fill={successColor} radius={[0, 0, 0, 0]} />
        <Bar dataKey="other" stackId="a" fill={dangerColor} radius={[4, 4, 0, 0]}>
          {chartData.map((_, i) => (
            <Cell key={i} fill={dangerColor} />
          ))}
        </Bar>
      </BarChart>
    </ChartCard>
  );
}

const tickStyle = { fill: "hsl(var(--muted-foreground))", fontSize: 11 };
const axisStyle = { stroke: "hsl(var(--border))" };

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactElement;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
