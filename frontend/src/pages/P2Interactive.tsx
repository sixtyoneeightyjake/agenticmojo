import { useEffect, useRef, useState } from "react";
import { p2CreateSession } from "../lib/api";
import { p2OpenWS } from "../lib/ws";

type ChatMsg =
  | { role: "assistant" | "user" | "system"; text: string }
  | any;

export default function P2Interactive() {
  const [appName, setAppName] = useState("");
  const [desc, setDesc] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const wsRef = useRef<ReturnType<typeof p2OpenWS> | null>(null);
  const [input, setInput] = useState("");

  useEffect(() => () => wsRef.current?.close(), []);

  async function onStart() {
    const { session_id } = await p2CreateSession({
      appName,
      description: desc,
    });
    setSessionId(session_id);
    wsRef.current = p2OpenWS(session_id, (msg) => {
      setChat((c) => [...c, msg]);
    });
    setChat([
      {
        role: "assistant",
        text: `Session ${session_id} ready. Tell me what to scaffold.`,
      },
    ]);
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
      <h1 className="text-2xl font-black tracking-wide">
        2P — Interactive Mode (trae-cli interactive)
      </h1>

      {!sessionId && (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="grid gap-2">
            <label className="text-xs uppercase opacity-70">App Name</label>
            <input
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              className="arcade-input"
            />
          </div>
          <div className="grid gap-2">
            <label className="text-xs uppercase opacity-70">Description</label>
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={3}
              className="arcade-input"
            />
          </div>
          <div className="md:col-span-2">
            <button onClick={onStart} className="arcade-button">
              Start 2P
            </button>
          </div>
        </div>
      )}

      {sessionId && (
        <div className="grid gap-3">
          <div className="rounded-lg border border-slate-700 bg-slate-900 p-3 h-[60vh] overflow-auto">
            {chat.map((m, i) => (
              <div key={i} className="mb-3">
                {m.role && (
                  <div
                    className={
                      m.role === "user"
                        ? "text-cyan-300"
                        : m.role === "assistant"
                        ? "text-fuchsia-300"
                        : "text-slate-300"
                    }
                  >
                    <b>{m.role.toUpperCase()}</b>: {m.text}
                  </div>
                )}
                {m.type === "proposal" && (
                  <div className="mt-2 grid gap-2">
                    {m.actions?.map((a: any) => (
                      <div key={a.id} className="rounded border border-slate-600 p-2">
                        <div className="font-semibold">{a.summary}</div>
                        <div className="mt-1 flex gap-2">
                          <button
                            className="rounded bg-emerald-600 px-2 py-1 text-sm"
                            onClick={() => onApprove(a.id)}
                          >
                            Approve
                          </button>
                          <button
                            className="rounded bg-rose-600 px-2 py-1 text-sm"
                            onClick={() => onReject(a.id)}
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {m.type === "diff" && (
                  <div className="mt-2">
                    {m.files?.map((f: any, j: number) => (
                      <details key={j} className="mb-2">
                        <summary className="cursor-pointer">🧩 {f.path}</summary>
                        <pre className="mt-1 overflow-auto rounded bg-slate-950 p-2 text-[12px]">
                          {f.patch}
                        </pre>
                      </details>
                    ))}
                  </div>
                )}
                {m.type === "question" && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {m.choices?.map((c: string, k: number) => (
                      <button
                        key={k}
                        className="rounded bg-blue-600 px-2 py-1 text-sm"
                        onClick={() => wsRef.current?.send({ type: "answer", text: c })}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendUser()}
              placeholder="Type to pair program with Mojo…"
              className="flex-1 arcade-input"
            />
            <button onClick={sendUser} className="arcade-button">Send</button>
          </div>
        </div>
      )}
    </div>
  );
}

