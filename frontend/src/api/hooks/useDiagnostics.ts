/**
 * React Query hooks for the Diagnostics tab (Task 3.3).
 *
 * Backend endpoints:
 *   POST /api/v1/diagnostics/ping                 -> PingResult
 *   POST /api/v1/diagnostics/link-test            -> PingResult
 *   GET  /api/v1/diagnostics/configuration-report -> ConfigurationReportResponse
 *   POST /api/v1/diagnostics/device-reset         -> DeviceResetResponse
 *
 * Notes:
 *   * Configuration-report is a `useQuery` with `enabled: false`: the user
 *     triggers it explicitly via `.refetch()` so we don't hammer the switch
 *     on navigation.
 *   * Ping and link test are mutations — they emit packets and we want the
 *     caller's "Run" button to be the sole trigger.
 *   * Device reset is a mutation that goes through `DangerConfirmDialog`;
 *     the backend rejects with 400 if `confirm_switch_host` doesn't match
 *     `settings.switch_host`, and with 403 if READ_ONLY=true.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost, type ApiError } from "@/api/client";
import type { components } from "@/api/schema";

export type PingRequest = components["schemas"]["PingRequest"];
export type LinkTestRequest = components["schemas"]["LinkTestRequest"];
export type DeviceResetRequest = components["schemas"]["DeviceResetRequest"];
export type PingResult = components["schemas"]["PingResult"];
export type ConfigurationReportResponse =
  components["schemas"]["ConfigurationReportResponse"];
export type DeviceResetResponse =
  components["schemas"]["DeviceResetResponse"];

export function usePing() {
  return useMutation<PingResult, ApiError, PingRequest>({
    mutationFn: (body) =>
      apiPost<PingResult, PingRequest>("/api/v1/diagnostics/ping", body),
  });
}

export function useLinkTest() {
  return useMutation<PingResult, ApiError, LinkTestRequest>({
    mutationFn: (body) =>
      apiPost<PingResult, LinkTestRequest>(
        "/api/v1/diagnostics/link-test",
        body,
      ),
  });
}

/**
 * Lazy configuration-report fetch. The caller presses "Generate" which
 * triggers `refetch()`; we never run on mount.
 */
export function useConfigurationReport() {
  return useQuery<ConfigurationReportResponse>({
    queryKey: ["diagnostics", "config-report"],
    queryFn: () =>
      apiGet<ConfigurationReportResponse>(
        "/api/v1/diagnostics/configuration-report",
      ),
    enabled: false,
  });
}

export function useDeviceReset() {
  return useMutation<DeviceResetResponse, ApiError, DeviceResetRequest>({
    mutationFn: (body) =>
      apiPost<DeviceResetResponse, DeviceResetRequest>(
        "/api/v1/diagnostics/device-reset",
        body,
      ),
  });
}
