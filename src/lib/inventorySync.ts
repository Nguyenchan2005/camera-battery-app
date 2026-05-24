import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { User } from "@supabase/supabase-js";
import type { CameraBatteryDatabase } from "./database";
import {
  getInitialSyncStatus,
  hasInventoryItems,
  inventoriesEqual,
  loadCloudInventory,
  makeInventorySnapshot,
  mergeInventorySnapshots,
  saveCloudInventory,
  validateInventoryIds,
  type InventorySnapshot,
} from "./cloudInventory";
import { getSupabaseConfigStatus, isSupabaseConfigured, supabase } from "./supabase";

function getAuthRedirectUrl(): string {
  const configuredUrl = import.meta.env.VITE_APP_URL as string | undefined;
  if (configuredUrl) return configuredUrl;

  return new URL(import.meta.env.BASE_URL, window.location.origin).toString();
}

export type InventorySyncStatus =
  | "local_only"
  | "signed_in"
  | "loading_cloud"
  | "syncing"
  | "synced"
  | "unsynced_changes"
  | "sync_error"
  | "offline_saved_locally";

export type InventoryConflictChoice = "local" | "cloud" | "merge";

export interface InventoryConflict {
  local: InventorySnapshot;
  cloud: InventorySnapshot;
}

export interface InventorySyncController {
  configured: boolean;
  missingConfig: string[];
  user: User | null;
  authLoading: boolean;
  authMessage: string | null;
  status: InventorySyncStatus;
  error: string | null;
  warnings: string[];
  conflict: InventoryConflict | null;
  signInWithEmail: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  resolveConflict: (choice: InventoryConflictChoice) => Promise<void>;
  retrySync: () => Promise<void>;
}

export function useInventorySync({
  db,
  myCameraIds,
  myBatteryIds,
  replaceCameras,
  replaceBatteries,
  online,
}: {
  db: CameraBatteryDatabase;
  myCameraIds: string[];
  myBatteryIds: string[];
  replaceCameras: (ids: string[]) => void;
  replaceBatteries: (ids: string[]) => void;
  online: boolean;
}): InventorySyncController {
  const configStatus = useMemo(() => getSupabaseConfigStatus(), []);
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(isSupabaseConfigured);
  const [authMessage, setAuthMessage] = useState<string | null>(null);
  const [status, setStatus] = useState<InventorySyncStatus>(() =>
    getInitialSyncStatus({ configured: isSupabaseConfigured, userId: null, online }),
  );
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [conflict, setConflict] = useState<InventoryConflict | null>(null);
  const readyUserIdRef = useRef<string | null>(null);
  const lastCloudRef = useRef<InventorySnapshot | null>(null);
  const syncTimerRef = useRef<number | null>(null);
  const latestLocalRef = useRef(makeInventorySnapshot(myCameraIds, myBatteryIds));

  useEffect(() => {
    latestLocalRef.current = makeInventorySnapshot(myCameraIds, myBatteryIds);
  }, [myCameraIds, myBatteryIds]);

  useEffect(() => {
    if (!supabase) {
      setAuthLoading(false);
      setStatus("local_only");
      return;
    }

    let active = true;
    supabase.auth
      .getSession()
      .then(({ data, error: sessionError }) => {
        if (!active) return;
        if (sessionError) {
          setError(sessionError.message);
          setStatus("sync_error");
        }
        setUser(data.session?.user ?? null);
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setStatus(session?.user ? "signed_in" : "local_only");
      setAuthMessage(null);
      setError(null);
      setConflict(null);
      readyUserIdRef.current = null;
      lastCloudRef.current = null;
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!supabase || authLoading) {
      if (!supabase) setStatus("local_only");
      return;
    }

    if (!user) {
      readyUserIdRef.current = null;
      lastCloudRef.current = null;
      setConflict(null);
      setStatus("local_only");
      return;
    }

    if (!online) {
      setStatus("offline_saved_locally");
      return;
    }

    let cancelled = false;
    const local = makeInventorySnapshot(myCameraIds, myBatteryIds);

    async function loadAndReconcile() {
      if (!supabase || !user) return;
      setStatus("loading_cloud");
      setError(null);
      try {
        const cloudRaw = await loadCloudInventory(supabase, user.id);
        if (cancelled) return;

        if (!cloudRaw) {
          const saved = await saveCloudInventory(supabase, user.id, local);
          if (cancelled) return;
          lastCloudRef.current = saved;
          readyUserIdRef.current = user.id;
          setStatus("synced");
          return;
        }

        const validated = validateInventoryIds(cloudRaw, db, "cloud");
        setWarnings(validated.warnings);
        const cloud = validated.inventory;

        if (!hasInventoryItems(cloud) && hasInventoryItems(local)) {
          const saved = await saveCloudInventory(supabase, user.id, local);
          if (cancelled) return;
          lastCloudRef.current = saved;
          readyUserIdRef.current = user.id;
          setStatus("synced");
          return;
        }

        if (!hasInventoryItems(local) || inventoriesEqual(local, cloud)) {
          replaceCameras(cloud.myCameraIds);
          replaceBatteries(cloud.myBatteryIds);
          lastCloudRef.current = cloud;
          readyUserIdRef.current = user.id;
          setStatus("synced");
          return;
        }

        lastCloudRef.current = cloud;
        setConflict({ local, cloud });
        setStatus("unsynced_changes");
      } catch (loadError) {
        if (cancelled) return;
        setError(loadError instanceof Error ? loadError.message : String(loadError));
        setStatus("sync_error");
      }
    }

    if (readyUserIdRef.current !== user.id && !conflict) {
      loadAndReconcile();
    }

    return () => {
      cancelled = true;
    };
  }, [authLoading, conflict, db, myBatteryIds, myCameraIds, online, replaceBatteries, replaceCameras, user]);

  const syncNow = useCallback(
    async (inventory: InventorySnapshot) => {
      if (!supabase || !user) return;
      if (!online) {
        setStatus("offline_saved_locally");
        return;
      }

      setStatus("syncing");
      setError(null);
      try {
        const validated = validateInventoryIds(inventory, db, "local");
        setWarnings((current) => [...current.filter((item) => !item.startsWith("local ")), ...validated.warnings]);
        const saved = await saveCloudInventory(supabase, user.id, validated.inventory);
        lastCloudRef.current = saved;
        readyUserIdRef.current = user.id;
        setStatus("synced");
      } catch (syncError) {
        setError(syncError instanceof Error ? syncError.message : String(syncError));
        setStatus("sync_error");
      }
    },
    [db, online, user],
  );

  useEffect(() => {
    if (!supabase || !user || authLoading || conflict || readyUserIdRef.current !== user.id) return;
    const local = makeInventorySnapshot(myCameraIds, myBatteryIds);
    if (lastCloudRef.current && inventoriesEqual(local, lastCloudRef.current)) {
      return;
    }
    if (!online) {
      setStatus("offline_saved_locally");
      return;
    }

    setStatus("unsynced_changes");
    if (syncTimerRef.current) window.clearTimeout(syncTimerRef.current);
    syncTimerRef.current = window.setTimeout(() => {
      syncNow(local);
    }, 1500);

    return () => {
      if (syncTimerRef.current) window.clearTimeout(syncTimerRef.current);
    };
  }, [authLoading, conflict, myBatteryIds, myCameraIds, online, syncNow, user]);

  async function signInWithEmail(email: string) {
    if (!supabase) return;
    setAuthLoading(true);
    setAuthMessage(null);
    setError(null);
    try {
      const { error: signInError } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: getAuthRedirectUrl() },
      });
      if (signInError) throw new Error(signInError.message);
      setAuthMessage("Magic link sent. Check your email to sign in.");
    } catch (signInError) {
      setError(signInError instanceof Error ? signInError.message : String(signInError));
      setStatus("sync_error");
    } finally {
      setAuthLoading(false);
    }
  }

  async function signOut() {
    if (!supabase) return;
    setAuthLoading(true);
    setAuthMessage(null);
    try {
      const { error: signOutError } = await supabase.auth.signOut();
      if (signOutError) throw new Error(signOutError.message);
      setUser(null);
      setStatus("local_only");
    } catch (signOutError) {
      setError(signOutError instanceof Error ? signOutError.message : String(signOutError));
      setStatus("sync_error");
    } finally {
      setAuthLoading(false);
    }
  }

  async function resolveConflict(choice: InventoryConflictChoice) {
    if (!conflict || !user || !supabase) return;
    const selected =
      choice === "local"
        ? conflict.local
        : choice === "cloud"
          ? conflict.cloud
          : mergeInventorySnapshots(conflict.local, conflict.cloud);

    setConflict(null);
    replaceCameras(selected.myCameraIds);
    replaceBatteries(selected.myBatteryIds);
    await syncNow(selected);
  }

  async function retrySync() {
    if (!supabase || !user) return;
    await syncNow(latestLocalRef.current);
  }

  return {
    configured: configStatus.configured,
    missingConfig: configStatus.missing,
    user,
    authLoading,
    authMessage,
    status,
    error,
    warnings,
    conflict,
    signInWithEmail,
    signOut,
    resolveConflict,
    retrySync,
  };
}
