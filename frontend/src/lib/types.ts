export type RunState = "queued" | "running" | "done" | "error";

export type RunEvent =
  | { type: "status"; runId: string; state: RunState; message?: string }
  | {
      type: "step";
      index: number;
      tool:
        | "bash"
        | "edit"
        | "sequential_thinking"
        | "test"
        | "commit";
      summary: string;
    }
  | { type: "output"; tool: string; text: string }
  | { type: "diff"; files: FileDiff[] }
  | { type: "metrics"; coverage?: number; refactor?: number; combo?: number }
  | { type: "error"; message: string };

export type FileDiff = { path: string; patch: string };

