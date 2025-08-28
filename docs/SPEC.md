# SPEC.md — Agent Mojo Arcade UI

Late‑90s/early‑2000s side‑scroll brawler styling. Two paths:

* **1P — Run Mode** → `trae-cli run`
* **2P — Interactive Mode** → `trae-cli interactive`

Front end: Vite + React + TypeScript + Tailwind. 2P chat uses CopilotKit UI or headless + our WS bridge. Backend remains FastAPI with minimal new routes.

---

## App Structure (frontend)

```
frontend/
  src/
    main.tsx
    App.tsx
    routes.tsx
    lib/
      api.ts
      stream.ts
      ws.ts
      types.ts
    pages/
      P1Run.tsx
      P2Interactive.tsx
    components/
      ArcadeHeader.tsx
      ModePanel.tsx
      HUD.tsx
      DiffViewer.tsx
      LogStream.tsx
    styles/
      index.css
```

---

## Shared Types — `src/lib/types.ts`

```ts
export type RunState = "queued" | "running" | "done" | "error";

export type RunEvent =
  | { type: "status"; runId: string; state: RunState; message?: string }
  | { type: "step"; index: number; tool: "bash" | "edit" | "sequential_thinking" | "test" | "commit"; summary: string }
  | { type: "output"; tool: string; text: string }
  | { type: "diff"; files: FileDiff[] }
  | { type: "metrics"; coverage?: number; refactor?: number; combo?: number }
  | { type: "error"; message: string };

export type FileDiff = { path: string; patch: string };
```

---

## API Helpers — `src/lib/api.ts`

```ts
export async function p1StartRun(payload: {
  git_url?: string;
  zip_token?: string;
  tasks?: string[];
  env?: Record<string, string>;
}) {
  const r = await fetch("/api/p1/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { run_id: string };
}

export async function p2CreateSession(payload: {
  appName: string;
  description: string;
  git_url?: string;
  zip_token?: string;
}) {
  const r = await fetch("/api/p2/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { session_id: string };
}

export async function uploadZip(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { zip_token: string };
}
```

---

## SSE & WS — `src/lib/stream.ts` and `src/lib/ws.ts`

```ts
// stream.ts — 1P SSE
export function p1OpenStream(runId: string, onEvent: (ev: MessageEvent) => void) {
  const es = new EventSource(`/api/p1/stream/${runId}`);
  es.onmessage = onEvent;
  es.onerror = () => es.close();
  return () => es.close();
}
```

```ts
// ws.ts — 2P WebSocket
export function p2OpenWS(sessionId: string, onMsg: (m: any) => void) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/p2/ws/${sessionId}`);
  ws.onmessage = (ev) => onMsg(JSON.parse(ev.data));
  return {
    send: (m: any) => ws.send(JSON.stringify(m)),
    close: () => ws.close(),
  };
}
```

---

## P1 — Run Mode Page — `src/pages/P1Run.tsx`

```tsx
import { useEffect, useRef, useState } from "react";
import { p1StartRun } from "../lib/api";
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
      try { setEvents((e) => [...e, JSON.parse(ev.data)]); } catch {}
    });
    return off;
  }, [runId]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const r = await fetch("/api/upload", { method: "POST", body: new FormData().append("file", file) as any });
    const j = await r.json();
    setZipToken(j.zip_token);
  }

  async function onStart() {
    const payload: any = { tasks: tasks.split("\n").map(s => s.trim()).filter(Boolean) };
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
          <input value={gitUrl} onChange={(e)=>setGitUrl(e.target.value)} placeholder="https://github.com/user/repo.git" className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2"/>
        </div>
        <div className="grid gap-2">
          <label className="text-xs uppercase opacity-70">or Upload .zip</label>
          <div className="flex items-center gap-3">
            <input ref={fileRef} type="file" className="hidden" onChange={onUpload}/>
            <button className="rounded-lg border border-slate-600 px-3 py-2" onClick={()=>fileRef.current?.click()}>Choose File</button>
            <span className="text-sm opacity-70">{zipToken ? `zip token: ${zipToken.slice(0,8)}…` : "no file"}</span>
          </div>
        </div>
      </div>

      <div className="grid gap-2">
        <label className="text-xs uppercase opacity-70">Tasks (one per line)</label>
        <textarea value={tasks} onChange={(e)=>setTasks(e.target.value)} rows={5} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2" placeholder="Add feature X\nFix bug Y"/>
      </div>

      <div className="flex gap-3">
        <button onClick={onStart} disabled={!gitUrl && !zipToken} className="rounded-lg bg-fuchsia-600 px-4 py-2 font-semibold disabled:opacity-40">Start 1P</button>
        {runId && <span className="text-sm opacity-80">Run: {runId}</span>}
      </div>

      <section className="grid gap-3">
        <h2 className="text-lg font-bold">Live Log</h2>
        <div className="rounded-lg border border-slate-700 bg-black/60 p-3 h-80 overflow-auto text-sm">
          {events.map((e, i) => (
            <div key={i} className="mb-2 whitespace-pre-wrap">
              {e.type === "output" && <code>{e.text}</code>}
              {e.type === "step" && <div>🔧 <b>{e.tool}</b> — {e.summary}</div>}
              {e.type === "status" && <div>📡 {e.state}</div>}
              {e.type === "error" && <div className="text-red-300">⛔ {e.message}</div>}
              {e.type === "metrics" && <div>📊 coverage {e.coverage ?? "-"}% · refactor {e.refactor ?? "-"} · combo {e.combo ?? 0}x</div>}
              {e.type === "diff" && e.files?.map((f, j)=> (
                <details key={j} className="mt-1">
                  <summary className="cursor-pointer">🧩 {f.path}</summary>
                  <pre className="mt-1 overflow-auto rounded bg-slate-950 p-2 text-[12px]">{f.patch}</pre>
                </details>
              ))}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
```

---

## 2P — Interactive Page — `src/pages/P2Interactive.tsx`

```tsx
import { useEffect, useRef, useState } from "react";
import { p2CreateSession } from "../lib/api";
import { p2OpenWS } from "../lib/ws";

type ChatMsg = { role: "assistant" | "user" | "system"; text: string } | any;

export default function P2Interactive() {
  const [appName, setAppName] = useState("");
  const [desc, setDesc] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const wsRef = useRef<ReturnType<typeof p2OpenWS> | null>(null);
  const [input, setInput] = useState("");

  useEffect(() => () => wsRef.current?.close(), []);

  async function onStart() {
    const { session_id } = await p2CreateSession({ appName, description: desc });
    setSessionId(session_id);
    wsRef.current = p2OpenWS(session_id, (msg) => {
      setChat((c) => [...c, msg]);
    });
    setChat([{ role: "assistant", text: `Session ${session_id} ready. Tell me what to scaffold.` }]);
  }

  function sendUser() {
    const text = input.trim();
    if (!text) return;
    setChat((c) => [...c, { role: "user", text }]);
    wsRef.current?.send({ type: "answer", text });
    setInput("");
  }

  function onApprove(actionId: string) {
    wsRef.current?.send({ type: "approve", actionId });
  }
  function onReject(actionId: string) {
    wsRef.current?.send({ type: "reject", actionId, reason: "Not now" });
  }

  return (
    <div className="mx-auto max-w-6xl p-6 grid gap-4">
      <h1 className="text-2xl font-black tracking-wide">2P — Interactive Mode (trae-cli interactive)</h1>

      {!sessionId && (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="grid gap-2">
            <label className="text-xs uppercase opacity-70">App Name</label>
            <input value={appName} onChange={(e)=>setAppName(e.target.value)} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2"/>
          </div>
          <div className="grid gap-2">
            <label className="text-xs uppercase opacity-70">Description</label>
            <textarea value={desc} onChange={(e)=>setDesc(e.target.value)} rows={3} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2"/>
          </div>
          <div className="md:col-span-2">
            <button onClick={onStart} className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold">Start 2P</button>
          </div>
        </div>
      )}

      {sessionId && (
        <div className="grid gap-3">
          <div className="rounded-lg border border-slate-700 bg-slate-900 p-3 h-[60vh] overflow-auto">
            {chat.map((m, i) => (
              <div key={i} className="mb-3">
                {m.role && (
                  <div className={m.role === "user" ? "text-cyan-300" : m.role === "assistant" ? "text-fuchsia-300" : "text-slate-300"}>
                    <b>{m.role.toUpperCase()}</b>: {m.text}
                  </div>
                )}
                {/* proposals */}
                {m.type === "proposal" && (
                  <div className="mt-2 grid gap-2">
                    {m.actions?.map((a: any) => (
                      <div key={a.id} className="rounded border border-slate-600 p-2">
                        <div className="font-semibold">{a.summary}</div>
                        <div className="mt-1 flex gap-2">
                          <button className="rounded bg-emerald-600 px-2 py-1 text-sm" onClick={()=>onApprove(a.id)}>Approve</button>
                          <button className="rounded bg-rose-600 px-2 py-1 text-sm" onClick={()=>onReject(a.id)}>Reject</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {/* diffs */}
                {m.type === "diff" && (
                  <div className="mt-2">
                    {m.files?.map((f: any, j: number) => (
                      <details key={j} className="mb-2">
                        <summary className="cursor-pointer">🧩 {f.path}</summary>
                        <pre className="mt-1 overflow-auto rounded bg-slate-950 p-2 text-[12px]">{f.patch}</pre>
                      </details>
                    ))}
                  </div>
                )}
                {/* questions */}
                {m.type === "question" && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {m.choices?.map((c: string, k: number) => (
                      <button key={k} className="rounded bg-blue-600 px-2 py-1 text-sm" onClick={()=>wsRef.current?.send({ type:"answer", text:c })}>{c}</button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <input value={input} onChange={(e)=>setInput(e.target.value)} onKeyDown={(e)=> e.key==='Enter' && sendUser()} placeholder="Type to pair program with Mojo…" className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2"/>
            <button onClick={sendUser} className="rounded-lg bg-fuchsia-600 px-4 py-2 font-semibold">Send</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## Minimal Routes Hookup — `src/routes.tsx`

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AgentMojoArcadeLanding from "./App"; // your landing
import P1Run from "./pages/P1Run";
import P2Interactive from "./pages/P2Interactive";

export default function AppRoutes(){
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AgentMojoArcadeLanding/>} />
        <Route path="/p1" element={<P1Run/>} />
        <Route path="/p2" element={<P2Interactive/>} />
      </Routes>
    </BrowserRouter>
  );
}
```

(If your current `App.tsx` is the landing mock, swap the exported default there or wrap it inside this router.)

---

## Backend (FastAPI) sketch

**1P:**

* `POST /api/p1/run` → returns `{ run_id }` and spawns `trae-cli run …` in background.
* `GET /api/p1/stream/{run_id}` → SSE of `RunEvent`.

**2P:**

* `POST /api/p2/session` → returns `{ session_id }` and allocates interactive context.
* `GET /api/p2/ws/{session_id}` → WebSocket; proxy I/O to `trae-cli interactive` loop.

**Upload (optional):**

* `POST /api/upload` → `{ zip_token }`; server unpacks and returns a token/path for later use.

---

## Acceptance

* `/` renders split screen; buttons lead to `/p1` and `/p2`.
* `/p1` starts runs with either Git URL or zip token; live log & diffs stream.
* `/p2` opens a WS session; assistant/user messages show; proposals, questions, diffs render; Approve/Reject round‑trips.
* Error states show non-blocking toasts; dark arcade theme consistent.

```
```
This does not complete the implementation by any means, things such as 	wire the landing mock’s Start buttons to /p1 and /p2,
	•	or convert the 2P chat to CopilotKit’s <CopilotPopup /> with an action that calls your backend,
still need done, but this is a great start.