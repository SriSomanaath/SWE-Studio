import type { TrajectoryStep } from "@/lib/types";

import { CodeBlock } from "./CodeBlock";

export function StepView({ step, index }: { step: TrajectoryStep; index: number }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Step {index + 1}</h2>
        {step.action && (
          <p className="mt-1 font-mono text-sm text-muted-foreground">{step.action}</p>
        )}
      </div>

      {step.thought && (
        <Section label="Thought">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{step.thought}</p>
        </Section>
      )}

      {step.action && (
        <Section label="Action">
          <CodeBlock>{step.action}</CodeBlock>
        </Section>
      )}

      {step.observation && (
        <Section label="Observation">
          <CodeBlock>{step.observation}</CodeBlock>
        </Section>
      )}

      {step.response && step.response !== step.thought && (
        <Section label="Response">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{step.response}</p>
        </Section>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </h3>
      {children}
    </div>
  );
}
