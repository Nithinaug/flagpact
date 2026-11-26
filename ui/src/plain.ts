const STEPS: Record<string, string> = {
  "segment created": "Created a rule that keeps older versions on the old value",
  "segment updated": "Updated the rule for older versions",
  "override created": "Saved the old value for those versions",
  "override updated": "Updated the old value for those versions",
  "override moved to highest priority": "Made that rule take priority",
  "default changed": "Published the new value to everyone else",
  "default restored": "Restored the previous value",
  "segment and override removed": "Removed the rule for older versions",
};

const TYPES: Record<string, string> = {
  string: "text",
  number: "number",
  boolean: "yes or no",
  array: "list",
  object: "group",
  null: "empty",
  missing: "not present",
};

export function plainReason(reason: string): string {
  const missing = reason.match(/required path '([^']+)' is missing/);
  if (missing) return `Needs "${missing[1]}", which is missing`;
  const changed = reason.match(/path '([^']+)' is (\w+), contract has (.+)/);
  if (changed) return `"${changed[1]}" is now ${plainType(changed[2])}, this version expects ${plainType(changed[3])}`;
  if (reason === "replay failed") return "Its own tests fail with this value";
  if (reason === "replay passed") return "Its own tests pass with this value";
  if (reason.includes("replay not run")) return "Not tested yet";
  if (reason.startsWith("no contract recorded")) return "No recorded behaviour for this version";
  if (reason === "waiting for a pending change") return "Waiting for a change";
  return reason;
}

export function plainStep(step: string): string {
  return STEPS[step] ?? step;
}

export function plainType(type: string): string {
  return type
    .split("|")
    .map((part) => TYPES[part] ?? part)
    .join(" or ");
}

export function plainCrash(output: string): string {
  const missing = output.match(/missing '([^']+)'/);
  if (missing) return `Crashes: it needs "${missing[1]}" but that is gone`;
  return `Crashes: ${output}`;
}
