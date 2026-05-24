import { useEffect, useState } from "react";

export function useOnlineStatus() {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  const [serviceWorkerReady, setServiceWorkerReady] = useState(false);

  useEffect(() => {
    function sync() {
      setOnline(navigator.onLine);
    }

    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.ready
        .then(() => setServiceWorkerReady(true))
        .catch(() => setServiceWorkerReady(false));
    }

    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  return { online, serviceWorkerReady };
}
