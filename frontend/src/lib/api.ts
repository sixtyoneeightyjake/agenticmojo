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

