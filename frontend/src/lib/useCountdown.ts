import { useEffect, useRef, useState } from "react";
import { secondsLeft } from "./format";

/** Seconds left on a hold, driven by the server clock (offset captured when the booking was fetched). */
export function useCountdown(expiresAt: string | null | undefined, serverTime: string | undefined) {
  const fetchedAt = useRef(Date.now());
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!expiresAt || !serverTime) { setLeft(null); return; }
    fetchedAt.current = Date.now();
    const tick = () => setLeft(secondsLeft(expiresAt, serverTime, fetchedAt.current));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiresAt, serverTime]);
  return left;
}
