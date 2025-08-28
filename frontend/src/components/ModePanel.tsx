import { PropsWithChildren } from "react";

export default function ModePanel({ title, badge, children }: PropsWithChildren<{ title: string; badge: string }>) {
  return (
    <section className="arcade-panel">
      <div className="flex items-center gap-3">
        <div className="text-3xl font-black text-amber-400">{badge}</div>
        <h2 className="text-xl font-extrabold tracking-wide">{title}</h2>
      </div>
      <div className="mt-3 grid gap-3">{children}</div>
    </section>
  );
}

