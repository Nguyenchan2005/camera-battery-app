import { useEffect, useMemo, useState } from "react";

export function readStoredIds(key: string): string[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function writeStoredIds(key: string, ids: string[]): void {
  window.localStorage.setItem(key, JSON.stringify([...new Set(ids)]));
}

export function useLocalStorageIds(key: string) {
  const [ids, setIds] = useState<string[]>(() => readStoredIds(key));

  useEffect(() => {
    writeStoredIds(key, ids);
  }, [ids, key]);

  return useMemo(
    () => ({
      ids,
      add(id: string) {
        setIds((current) => (current.includes(id) ? current : [...current, id]));
      },
      remove(id: string) {
        setIds((current) => current.filter((item) => item !== id));
      },
      clear() {
        setIds([]);
      },
      replace(nextIds: string[]) {
        setIds([...new Set(nextIds)]);
      },
    }),
    [ids],
  );
}
