// ws.ts — 2P WebSocket helper
export function p2OpenWS(sessionId: string, onMsg: (m: any) => void) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/p2/ws/${sessionId}`);
  ws.onmessage = (ev) => onMsg(JSON.parse(ev.data));
  return {
    send: (m: any) => ws.send(JSON.stringify(m)),
    close: () => ws.close(),
  };
}

