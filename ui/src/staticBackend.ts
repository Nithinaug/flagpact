import fixtures from "./static/fixtures.json";

type Phase = "start" | "applied" | "published" | "outside" | "protected" | "staged";

const fx = fixtures as any;
const SAMPLE_REPO = "github.com/nithinaug/flagpact-sample-app";

let phase: Phase = "start";
let includeMissing = true;

const key = (p: Phase = phase, im: boolean = includeMissing) => {
  const free = p === "start" || p === "outside" || p === "protected";
  return `${p}|${(free ? im : includeMissing) ? "1" : "0"}`;
};

const sorted = (v: unknown): unknown =>
  Array.isArray(v)
    ? v.map(sorted)
    : v && typeof v === "object"
      ? Object.fromEntries(Object.keys(v as object).sort().map((k) => [k, sorted((v as any)[k])]))
      : v;
const same = (a: unknown, b: unknown) => JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));

class ReplayError extends Error {}

function kind(value: unknown): "live" | "break" {
  if (same(value, fx.state[key()].value)) return "live";
  if (same(value, fx.break_value)) return "break";
  throw new ReplayError("This is a recorded replay, so it only knows the sample change. Click Try a breaking change, or Reset to live.");
}

const copy = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

export async function replay(method: string, path: string, body: any): Promise<unknown> {
  await new Promise((resolve) => setTimeout(resolve, path === "/api/watch" ? 0 : 350));
  const route = `${method} ${path}`;
  const im = body && typeof body.include_missing === "boolean" ? body.include_missing : includeMissing;

  switch (route) {
    case "GET /api/state":
      return copy(fx.state[key()]);
    case "GET /api/watch":
      return { ...copy(fx.watch[key()]), checked_at: Date.now() / 1000 };
    case "POST /api/check": {
      const k = kind(body.value);
      const set = k === "live" ? fx.check_live : fx.check_break;
      return copy(set[key(phase, im)][body.replay ? "full" : "quick"]);
    }
    case "POST /api/plan": {
      const k = kind(body.value);
      return copy((k === "live" ? fx.plan_live : fx.plan_break)[key(phase, im)]);
    }
    case "POST /api/apply": {
      if (phase !== "start") throw new ReplayError("A fix is already applied. Undo it first.");
      kind(body.value);
      phase = "applied";
      includeMissing = im;
      return {
        steps: ["segment created", "override created", "override moved to highest priority"],
        cells: copy(fx.apply_cells[`x|${im ? "1" : "0"}`]),
      };
    }
    case "POST /api/publish":
      if (phase !== "applied") throw new ReplayError("Apply the fix first.");
      phase = "published";
      return { steps: ["default changed"] };
    case "POST /api/rollback": {
      const steps = phase === "published" || phase === "staged" || phase === "protected" ? ["default restored"] : [];
      steps.push("segment and override removed");
      phase = "start";
      includeMissing = true;
      return { steps };
    }
    case "POST /api/render": {
      if (body && body.value !== undefined && !same(body.value, fx.state[key()].value)) {
        kind(body.value);
        return copy(fx.render_break[key()]);
      }
      return copy(fx.render_live[key()]);
    }
    case "POST /api/stages": {
      const base = copy(fx.stages[key("start", im)]);
      if (phase === "applied" || phase === "published" || phase === "staged" || phase === "protected") {
        return { ...base, current: 0, published: phase !== "applied" };
      }
      return base;
    }
    case "POST /api/stage-next": {
      if (phase !== "start") throw new ReplayError("A fix or stage is already applied. Undo it first.");
      kind(body.value);
      phase = "staged";
      includeMissing = im;
      return { steps: ["segment created", "override created", "override moved to highest priority", "default changed"], stage: 0, done: true };
    }
    case "POST /api/stage-back": {
      if (phase === "start" || phase === "outside") throw new ReplayError("No stage is applied.");
      phase = "start";
      includeMissing = true;
      return { steps: ["default restored", "segment and override removed"], stage: -1 };
    }
    case "POST /api/outside-edit":
      if (phase !== "start") throw new ReplayError("Undo the fix first, then simulate the edit.");
      phase = "outside";
      return { value: copy(fx.outside_value) };
    case "POST /api/protect":
      if (phase !== "outside") throw new ReplayError("The live value is safe, there is nothing to protect.");
      phase = "protected";
      return { steps: ["segment created", "override created", "override moved to highest priority"], limit: fx.limit };
    case "POST /api/restore":
      if (phase !== "outside") throw new ReplayError("There is no earlier safe value to restore.");
      phase = "start";
      includeMissing = true;
      return { value: copy(fx.start_value) };
    case "POST /api/import": {
      const source = String(body.source ?? "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\.git$/, "").replace(/\/$/, "");
      if (source !== SAMPLE_REPO) {
        throw new ReplayError("This replay can only scan the sample repository https://github.com/Nithinaug/flagpact-sample-app. Install flagpact with pip to scan your own.");
      }
      return copy(fx.import_sample);
    }
    case "POST /api/rehearse":
      throw new ReplayError("Rehearsal needs a running Flagsmith to clone, so it is not part of this replay.");
    default:
      throw new ReplayError("Not available in the replay.");
  }
}
