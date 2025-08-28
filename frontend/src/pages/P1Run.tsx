import { useEffect, useRef, useState } from "react";
import { p1StartRun, uploadZip } from "../lib/api";
import { p1OpenStream } from "../lib/stream";
import type { RunEvent } from "../lib/types";

export default function P1Run() {
  const [gitUrl, setGitUrl] = useState("");
  const [tasks, setTasks] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [zipToken, setZipToken] = useState<string | undefined>();
  const [runId, setRunId] = useState<string | undefined>();
  const [events, setEvents] = useState<RunEvent[]>([]);

  useEffect(() => {
    if (!runId) return;
    const off = p1OpenStream(runId, (ev) => {
      try {
        setEvents((e) => [...e, JSON.parse(ev.data)]);
      } catch {}
    });
    return off;
  }, [runId]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { zip_token } = await uploadZip(file);
      setZipToken(zip_token);
    } catch (err) {
      console.error(err);
      alert("Upload failed");
    }
  }

  async function onStart() {
    const payload: any = {
      tasks: tasks
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (gitUrl) payload.git_url = gitUrl;
    if (zipToken) payload.zip_token = zipToken;
    const { run_id } = await p1StartRun(payload);
    setRunId(run_id);
    setEvents([]);
  }

  return (
    <div className="mx-auto max-w-6xl p-6 grid gap-4">
      <h1 className="text-2xl font-black tracking-wide">1P — Run Mode (trae-cli run)</h1>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="grid gap-2">
          <label className="text-xs uppercase opacity-70">Git URL</label>
          <input
            value={gitUrl}
            onChange={(e) => setGitUrl(e.target.value)}
            placeholder="https://github.com/user/repo.git"
            className="arcade-input"
          />
        </div>
        <div className="grid gap-2">
          <label className="text-xs uppercase opacity-70">or Upload .zip</label>
          <div className="flex items-center gap-3">
            <input ref={fileRef} type="file" className="hidden" onChange={onUpload} />
            <button
              className="rounded-lg border border-slate-600 px-3 py-2"
              onClick={() => fileRef.current?.click()}
            >
              Choose File
            </button>
            <span className="text-sm opacity-70">
              {zipToken ? `zip token: ${zipToken.slice(0, 8)}…` : "no file"}
            </span>
          </div>
        </div>
      </div>

      <div className="grid gap-2">
        <label className="text-xs uppercase opacity-70">Tasks (one per line)</label>
        <textarea
          value={tasks}
          onChange={(e) => setTasks(e.target.value)}
          rows={5}
          className="arcade-input"
          placeholder={"Add feature X\nFix bug Y"}
        />
      </div>

      <div className="flex gap-3">
        <button
          onClick={onStart}
          disabled={!gitUrl && !zipToken}
          className="arcade-button-red disabled:opacity-40"
        >
          Start 1P
        </button>
        {runId && <span className="text-sm opacity-80">Run: {runId}</span>}
      </div>

      <section className="grid gap-3">
        <h2 className="text-lg font-bold">Live Log</h2>
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
      </section>
    </div>
  );
}

