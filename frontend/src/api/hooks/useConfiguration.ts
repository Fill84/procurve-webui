/**
 * React Query hooks for the Configuration tab (Task 3.5).
 *
 * Sub-task 3.5a covers system info + IP config. More hooks land in 3.5b
 * (ports), 3.5c (features), 3.5d (QoS), 3.5e (support).
 *
 * Backend endpoints (this sub-task):
 *   GET  /api/v1/configuration/system   -> SystemInfoPage
 *   PUT  /api/v1/configuration/system   -> ConfigWriteAck   (autobackup only)
 *   GET  /api/v1/configuration/ip       -> IpConfigPage
 *   PUT  /api/v1/configuration/ip       -> ConfigWriteAck   (autobackup + host confirm)
 *   PUT  /api/v1/configuration/gateway  -> ConfigWriteAck   (autobackup only)
 *
 * Every mutation invalidates:
 *   1. Its own resource query (so the UI refetches the fresh state), and
 *   2. ["backups"]  (the pre-write autobackup is now on disk — the Backups
 *      tab should show it next time the user opens it).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPut, type ApiError } from "@/api/client";
import type { components } from "@/api/schema";

export type SystemInfoPage = components["schemas"]["SystemInfoPage"];
export type IpConfigPage = components["schemas"]["IpConfigPage"];
export type IpMode = components["schemas"]["IpMode"];

export type ConfigWriteAck = components["schemas"]["ConfigWriteAck"];

export type SetSystemInfoRequest =
  components["schemas"]["SetSystemInfoRequest"];
export type SetSystemInfoBody = components["schemas"]["SetSystemInfoBody"];

export type SetIpConfigRequest = components["schemas"]["SetIpConfigRequest"];
export type SetIpConfigBody = components["schemas"]["SetIpConfigBody"];

export type SetDefaultGatewayRequest =
  components["schemas"]["SetDefaultGatewayRequest"];
export type SetDefaultGatewayBody =
  components["schemas"]["SetDefaultGatewayBody"];

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

export function useSystemInfo() {
  return useQuery<SystemInfoPage>({
    queryKey: ["configuration", "system"],
    queryFn: () => apiGet<SystemInfoPage>("/api/v1/configuration/system"),
  });
}

export function useIpConfig() {
  return useQuery<IpConfigPage>({
    queryKey: ["configuration", "ip"],
    queryFn: () => apiGet<IpConfigPage>("/api/v1/configuration/ip"),
  });
}

// ---------------------------------------------------------------------------
// Writes
// ---------------------------------------------------------------------------

export function useSetSystemInfo() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetSystemInfoBody>({
    mutationFn: (body) =>
      apiPut<ConfigWriteAck, SetSystemInfoBody>(
        "/api/v1/configuration/system",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["configuration", "system"] });
      // System name/location/contact also live on the Identity page (SNMP
      // sysName/sysLocation/sysContact), so refresh that too.
      void qc.invalidateQueries({ queryKey: ["identity"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

export function useSetIpConfig() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetIpConfigBody>({
    mutationFn: (body) =>
      apiPut<ConfigWriteAck, SetIpConfigBody>(
        "/api/v1/configuration/ip",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["configuration", "ip"] });
      // Identity echoes the management IP — refresh it so the status bar
      // and identity card catch up (or surface the disconnect quickly).
      void qc.invalidateQueries({ queryKey: ["identity"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

export function useSetDefaultGateway() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetDefaultGatewayBody>({
    mutationFn: (body) =>
      apiPut<ConfigWriteAck, SetDefaultGatewayBody>(
        "/api/v1/configuration/gateway",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["configuration", "ip"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}
