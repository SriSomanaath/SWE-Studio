"use client";

import { useEffect, useRef, useState } from "react";

export type StreamState = "idle" | "connecting" | "open" | "closed" | "error";

export interface StreamHandle<T> {
  state: StreamState;
  lastEvent: T | null;
  lastEventAt: number | null;
}

/**
 * Subscribe to a Server-Sent Events stream. The hook keeps the connection
 * alive while the component is mounted, exposes the most recent event, and
 * fires `onEvent` for each one.
 */
export function useEventStream<T = unknown>(
  url: string | null,
  onEvent?: (event: T) => void,
): StreamHandle<T> {
  const [state, setState] = useState<StreamState>("idle");
  const [lastEvent, setLastEvent] = useState<T | null>(null);
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);

  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!url) {
      setState("idle");
      return;
    }
    setState("connecting");
    const es = new EventSource(url);
    es.onopen = () => setState("open");
    es.onerror = () => setState("error");
    es.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data) as T;
        setLastEvent(parsed);
        setLastEventAt(Date.now());
        handlerRef.current?.(parsed);
      } catch {
        // ignore malformed events
      }
    };
    return () => {
      es.close();
      setState("closed");
    };
  }, [url]);

  return { state, lastEvent, lastEventAt };
}
