/**
 * React Query hooks for the Status endpoints exposed by the backend.
 *
 * Reads:
 *   GET  /api/v1/status/device                 — banner (state, cpu, etc.)
 *   GET  /api/v1/status/ports                  — per-port link / mode / labels
 *   GET  /api/v1/status/counters               — per-port packet counters
 *   GET  /api/v1/status/port-usage             — per-port utilisation chart
 *   GET  /api/v1/status/alert-log              — recent alert events
 *   GET  /api/v1/status/alerts/{idx}?dt=<ts>   — parsed event-detail page
 *
 * Writes (fault-log mutations — gated by READ_ONLY, no auto-backup):
 *   POST /api/v1/status/alerts/ack             — acknowledge selected events
 *   POST /api/v1/status/alerts/delete          — delete selected events
 *
 * Each read hook sets its own `refetchInterval` tuned to the signal's
 * expected churn rate. We intentionally do NOT use `refetchOnWindowFocus`
 * — main.tsx disables it globally — because we want deterministic cadence
 * on a dashboard that's often left open. The detail hook does NOT
 * auto-refresh (the dialog is short-lived and we don't want extra load).
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiGet, apiPost, type ApiError } from "@/api/client";
import type { components } from "@/api/schema";

type DeviceStatusBanner = components["schemas"]["DeviceStatusBanner"];
type PortStatusList = components["schemas"]["PortStatusList"];
type PortCountersList = components["schemas"]["PortCountersList"];
type PortUsageList = components["schemas"]["PortUsageList"];
type AlertLog = components["schemas"]["AlertLog"];
export type AlertDetail = components["schemas"]["AlertDetail"];
export type AlertEventRef = components["schemas"]["AlertEventRef"];
export type AckAlertsBody = components["schemas"]["AckAlertsBody"];
export type ConfigWriteAck = components["schemas"]["ConfigWriteAck"];

export function useDeviceStatus() {
  return useQuery<DeviceStatusBanner>({
    queryKey: ["status", "device"],
    queryFn: () => apiGet<DeviceStatusBanner>("/api/v1/status/device"),
    refetchInterval: 10_000,
  });
}

interface PollOptions {
  /**
   * Override the default poll cadence (ms), or `false` to disable polling.
   * Pages that already receive the same data another way (e.g. the port
   * detail page's WebSocket stream) should slow these down — every tick is
   * a scrape of a fragile switch CGI (read-safety rule).
   */
  refetchInterval?: number | false;
}

export function usePortStatus(options?: PollOptions) {
  return useQuery<PortStatusList>({
    queryKey: ["status", "ports"],
    queryFn: () => apiGet<PortStatusList>("/api/v1/status/ports"),
    refetchInterval: options?.refetchInterval ?? 5_000,
  });
}

export function usePortCounters(options?: PollOptions) {
  return useQuery<PortCountersList>({
    queryKey: ["status", "counters"],
    queryFn: () => apiGet<PortCountersList>("/api/v1/status/counters"),
    refetchInterval: options?.refetchInterval ?? 10_000,
  });
}

export function usePortUsage() {
  return useQuery<PortUsageList>({
    queryKey: ["status", "port-usage"],
    queryFn: () => apiGet<PortUsageList>("/api/v1/status/port-usage"),
    refetchInterval: 5_000,
  });
}

export function useAlertLog() {
  return useQuery<AlertLog>({
    queryKey: ["status", "alert-log"],
    queryFn: () => apiGet<AlertLog>("/api/v1/status/alert-log"),
    refetchInterval: 30_000,
  });
}

/**
 * Fetch the parsed detail page for one alert event.
 *
 * Disabled until both `index` and `tsCenti` are truthy (i.e. the dialog
 * has opened with a real selection). The query key includes both args so
 * opening a different event re-fetches.
 */
export function useAlertDetail(index: number | null, tsCenti: number | null) {
  const enabled = index !== null && index > 0 && tsCenti !== null && tsCenti > 0;
  return useQuery<AlertDetail>({
    queryKey: ["status", "alert-detail", index, tsCenti],
    queryFn: () =>
      apiGet<AlertDetail>(
        `/api/v1/status/alerts/${index}?dt=${tsCenti}`,
      ),
    enabled,
  });
}

export function useAcknowledgeAlerts() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, AckAlertsBody>({
    mutationFn: (body) =>
      apiPost<ConfigWriteAck, AckAlertsBody>(
        "/api/v1/status/alerts/ack",
        body,
      ),
    onSuccess: () => {
      // Re-fetch alert log so the table updates with the acked state.
      qc.invalidateQueries({ queryKey: ["status", "alert-log"] });
    },
  });
}

export function useDeleteAlerts() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, AckAlertsBody>({
    mutationFn: (body) =>
      apiPost<ConfigWriteAck, AckAlertsBody>(
        "/api/v1/status/alerts/delete",
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["status", "alert-log"] });
    },
  });
}
