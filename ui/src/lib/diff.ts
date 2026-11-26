export function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function leafPaths(value: unknown, prefix = ""): string[] {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => leafPaths(child, prefix ? `${prefix}.${key}` : key));
  }
  return prefix ? [prefix] : [];
}

export function pathPresent(value: unknown, path: string): boolean {
  let node: unknown = value;
  for (const part of path.split(".")) {
    if (node !== null && typeof node === "object" && part in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[part];
    } else {
      return false;
    }
  }
  return true;
}

export function fieldCounts(live: unknown, next: unknown): { removed: number; added: number } {
  const before = new Set(leafPaths(live));
  const after = new Set(leafPaths(next));
  return {
    removed: [...before].filter((p) => !after.has(p)).length,
    added: [...after].filter((p) => !before.has(p)).length,
  };
}

export function diffLines(a: string[], b: string[]): { removed: Set<number>; added: Set<number> } {
  const table: number[][] = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const removed = new Set<number>();
  const added = new Set<number>();
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      i++;
      j++;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      removed.add(i++);
    } else {
      added.add(j++);
    }
  }
  while (i < a.length) removed.add(i++);
  while (j < b.length) added.add(j++);
  return { removed, added };
}

export function parseBanner(output: string): { title: string; sub: string; button: string } {
  let text = output.replace("[BANNER] ", "");
  let button = "";
  const match = text.match(/\[([^\]]+)\]\s*$/);
  if (match) {
    button = match[1];
    text = text.slice(0, match.index).trim();
  }
  const [title, sub = ""] = text.split(" | ");
  return { title: title.trim(), sub: sub.trim(), button };
}

export function compactUsers(users: number | null): string {
  if (users === null) return "";
  return users >= 1000 ? `${(users / 1000).toFixed(1).replace(/\.0$/, "")}k` : String(users);
}

export function clock(date = new Date()): string {
  return date.toLocaleTimeString("en-GB", { hour12: false });
}
