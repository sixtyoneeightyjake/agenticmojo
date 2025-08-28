import type { RunEvent } from "../lib/types";

export default function LogStream({ events }: { events: RunEvent[] }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-black/60 p-3 h-80 overflow-auto text-sm">
      {events.map((e, i) => (
        <div key={i} className="mb-2 whitespace-pre-wrap">
          {e.type === "output" && <code>{e.text}</code>}
          {e.type === "step" && (
            <div>
              🔧 <b>{e.tool}</b> — {e.summary}
            </div>
          )}
          {e.type === "status" && <div>📡 {e.state}</div>}
          {e.type === "error" && (
            <div className="text-red-300">⛔ {e.message}</div>
          )}
          {e.type === "metrics" && (
            <div>
              📊 coverage {e.coverage ?? "-"}% · refactor {e.refactor ?? "-"} ·
              combo {e.combo ?? 0}x
            </div>
          )}
          {e.type === "diff" &&
            e.files?.map((f, j) => (
              <details key={j} className="mt-1">
                <summary className="cursor-pointer">🧩 {f.path}</summary>
                <pre className="mt-1 overflow-auto rounded bg-slate-950 p-2 text-[12px]">
                  {f.patch}
                </pre>
              </details>
            ))}
        </div>
      ))}
    </div>
  );
}

