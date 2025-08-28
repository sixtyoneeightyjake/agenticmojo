import { useNavigate } from "react-router-dom";

export default function AgentMojoArcadeLanding() {
  const nav = useNavigate();
  return (
    <div className="min-h-screen w-full">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex items-center justify-between">
          <h1 className="arcade-title text-3xl md:text-5xl">AGENT MOJO</h1>
          <div className="text-xs opacity-70">INSERT COIN ▸ 1</div>
        </header>

        <div className="grid gap-6 md:grid-cols-[1fr_auto_1fr] items-start">
          {/* 1P */}
          <section className="arcade-panel">
            <div className="flex items-center gap-3">
              <div className="text-3xl font-black text-amber-400">1P</div>
              <h2 className="text-xl font-extrabold tracking-wide">RUN MODE</h2>
            </div>
            <p className="mt-2 text-sm opacity-80">Run your tasks headlessly via trae-cli.</p>
            <button onClick={() => nav("/p1")} className="mt-4 arcade-button-red w-full text-center">
              START 1P (trae-cli run)
            </button>
          </section>

          {/* VS */}
          <div className="mx-auto hidden select-none md:block">
            <div className="rounded-full border-4 border-yellow-500 bg-slate-900 px-6 py-3 font-extrabold text-yellow-400 shadow-xl">
              VS
            </div>
          </div>

          {/* 2P */}
          <section className="arcade-panel">
            <div className="flex items-center gap-3">
              <div className="text-3xl font-black text-amber-400">2P</div>
              <h2 className="text-xl font-extrabold tracking-wide">CO-OP MODE</h2>
            </div>
            <p className="mt-2 text-sm opacity-80">Pair program interactively with Mojo.</p>
            <button onClick={() => nav("/p2")} className="mt-4 arcade-button w-full text-center">
              START 2P (interactive)
            </button>
          </section>
        </div>
      </div>
    </div>
  );
}

