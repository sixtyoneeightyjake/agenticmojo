// stream.ts — 1P SSE helper
export function p1OpenStream(
  runId: string,
  onEvent: (ev: MessageEvent) => void
) {
  const es = new EventSource(`/api/p1/stream/${runId}`);
  es.onmessage = onEvent;
  es.onerror = () => es.close();
  return () => es.close();
}

