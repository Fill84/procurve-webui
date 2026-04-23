/**
 * React hook that maintains a rolling buffer of per-second traffic samples
 * for a single port, streamed from the backend's `/ws/port-traffic` WebSocket
 * (Task 2.5).
 *
 * Frames on the wire look like:
 *
 *   {
 *     "timestamp": "2026-04-23T15:30:02Z",
 *     "poll_interval_s": 0.05,
 *     "ports": [{ "port": 1, "pkts_in_per_s": 100.0, ... }]
 *   }
 *
 * The very first frame after connection carries `ports: []` because the
 * backend needs two polls to compute rates; real samples begin on frame 2.
 *
 * Design decisions:
 *   - Relative WebSocket URL derived from `window.location` so that:
 *       * dev: vite proxies /ws to the backend (see vite.config.ts)
 *       * prod: same-origin, served by the FastAPI app behind nginx/Docker
 *     Protocol promoted to wss:// when the page itself is https.
 *   - We cap the buffer at `bufferSize` samples (default 240, i.e. two
 *     minutes at a 500 ms poll interval — the 50 ms interval the backend
 *     advertises is only sustainable on LAN benchmarks, so 240 is a safe
 *     upper bound either way). A simple slice-from-end keeps memory bounded.
 *   - Reconnect is user-driven: we expose a `reconnect()` callback that
 *     bumps a nonce to re-run the effect. Automatic reconnect loops are
 *     deliberately avoided so a broken backend doesn't spam WS connects.
 *   - Connection lifecycle mutates a single `connected` boolean. We also
 *     mark `connected=false` on `onerror` so the UI button is accurate even
 *     if `onclose` fires a tick later.
 */
import { useEffect, useRef, useState } from "react";

export interface PortSample {
  /** Frame timestamp in ms since epoch (convenient for Recharts XAxis). */
  t: number;
  pkts_in_per_s: number;
  pkts_out_per_s: number;
  mcast_in_per_s: number;
  mcast_out_per_s: number;
  bcast_in_per_s: number;
  bcast_out_per_s: number;
  errors_in_per_s: number;
}

interface WireFramePort {
  port: number;
  pkts_in_per_s: number;
  pkts_out_per_s: number;
  mcast_in_per_s: number;
  mcast_out_per_s: number;
  bcast_in_per_s: number;
  bcast_out_per_s: number;
  errors_in_per_s: number;
}

interface WireFrame {
  timestamp: string;
  poll_interval_s: number;
  ports: WireFramePort[];
}

export interface UseLivePortTrafficResult {
  samples: PortSample[];
  connected: boolean;
  reconnect: () => void;
}

export function useLivePortTraffic(
  port: number,
  bufferSize = 240,
): UseLivePortTrafficResult {
  const sessionKey = `${port}`;
  const [nonce, setNonce] = useState(0);
  const [lastKey, setLastKey] = useState(sessionKey);
  const [samples, setSamples] = useState<PortSample[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Reset the sample buffer during render whenever the port changes, so the
  // chart doesn't flash stale data while the new socket handshakes. React
  // discards the just-rendered output and re-renders with the new state, so
  // this is cheap and doesn't cause the "update during render" warning.
  if (lastKey !== sessionKey) {
    setLastKey(sessionKey);
    setSamples([]);
  }

  useEffect(() => {
    const url = new URL(window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/ws/port-traffic";
    url.search = "";
    url.hash = "";

    let cancelled = false;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!cancelled) setConnected(true);
    };
    ws.onclose = () => {
      if (!cancelled) setConnected(false);
    };
    ws.onerror = () => {
      if (!cancelled) setConnected(false);
    };
    ws.onmessage = (ev) => {
      if (cancelled) return;
      let frame: WireFrame;
      try {
        frame = JSON.parse(ev.data as string) as WireFrame;
      } catch {
        return; // Malformed frame — skip quietly.
      }
      if (!Array.isArray(frame.ports) || frame.ports.length === 0) {
        // First "baseline" frame has ports: []. Nothing to plot yet.
        return;
      }
      const p = frame.ports.find((pp) => pp.port === port);
      if (!p) return;
      const sample: PortSample = {
        t: new Date(frame.timestamp).getTime(),
        pkts_in_per_s: p.pkts_in_per_s,
        pkts_out_per_s: p.pkts_out_per_s,
        mcast_in_per_s: p.mcast_in_per_s,
        mcast_out_per_s: p.mcast_out_per_s,
        bcast_in_per_s: p.bcast_in_per_s,
        bcast_out_per_s: p.bcast_out_per_s,
        errors_in_per_s: p.errors_in_per_s,
      };
      setSamples((prev) => {
        const next = prev.length >= bufferSize
          ? [...prev.slice(prev.length - bufferSize + 1), sample]
          : [...prev, sample];
        return next;
      });
    };

    return () => {
      cancelled = true;
      // Only actively close OPEN/CONNECTING sockets; closing a CLOSED one is
      // a no-op but emits noisy browser warnings on some builds.
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      wsRef.current = null;
    };
  }, [port, bufferSize, nonce]);

  return {
    samples,
    connected,
    reconnect: () => setNonce((n) => n + 1),
  };
}
