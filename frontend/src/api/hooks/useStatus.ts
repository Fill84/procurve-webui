/**
 * React Query hooks for the four read-only Status endpoints exposed by the
 * backend:
 *
 *   GET /api/v1/status/device     — banner (state, cpu, etc.)
 *   GET /api/v1/status/ports      — per-port link / mode / labels
 *   GET /api/v1/status/counters   — per-port packet counters
 *   GET /api/v1/status/alert-log  — recent alert events
 *
 * Each hook sets its own `refetchInterval` tuned to the signal's expected
 * churn rate: ports link flaps fastest so poll at 5 s; banner and counters
 * shift slowly so poll at 10 s; the alert log is mostly idle so 30 s is
 * plenty. We intentionally do NOT use `refetchOnWindowFocus` — main.tsx
 * disables it globally — because we want deterministic cadence on a
 * dashboard that's often left open.
 */
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import type { components } from "@/api/schema";

type DeviceStatusBanner = components["schemas"]["DeviceStatusBanner"];
type PortStatusList = components["schemas"]["PortStatusList"];
type PortCountersList = components["schemas"]["PortCountersList"];
type PortUsageList = components["schemas"]["PortUsageList"];
type AlertLog = components["schemas"]["AlertLog"];

export function useDeviceStatus() {
  return useQuery<DeviceStatusBanner>({
    queryKey: ["status", "device"],
    queryFn: () => apiGet<DeviceStatusBanner>("/api/v1/status/device"),
    refetchInterval: 10_000,
  });
}

export function usePortStatus() {
  return useQuery<PortStatusList>({
    queryKey: ["status", "ports"],
    queryFn: () => apiGet<PortStatusList>("/api/v1/status/ports"),
    refetchInterval: 5_000,
  });
}

export function usePortCounters() {
  return useQuery<PortCountersList>({
    queryKey: ["status", "counters"],
    queryFn: () => apiGet<PortCountersList>("/api/v1/status/counters"),
    refetchInterval: 10_000,
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
