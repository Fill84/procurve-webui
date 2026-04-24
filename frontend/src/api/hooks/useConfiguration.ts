/**
 * React Query hooks for the Configuration tab (Task 3.5).
 *
 * Sub-tasks 3.5a (system + IP), 3.5b (ports), 3.5c (device features +
 * fault detection + monitor + bob-ports). More hooks land in 3.5d (QoS)
 * and 3.5e (support URLs).
 *
 * Backend endpoints:
 *   GET  /api/v1/configuration/system            -> SystemInfoPage
 *   PUT  /api/v1/configuration/system            -> ConfigWriteAck   (autobackup only)
 *   GET  /api/v1/configuration/ip                -> IpConfigPage
 *   PUT  /api/v1/configuration/ip                -> ConfigWriteAck   (autobackup + host confirm)
 *   PUT  /api/v1/configuration/gateway           -> ConfigWriteAck   (autobackup only)
 *   GET  /api/v1/configuration/ports             -> PortConfigList
 *   GET  /api/v1/configuration/ports/{port}      -> PortForm
 *   PUT  /api/v1/configuration/ports/{port}      -> ConfigWriteAck   (autobackup only)
 *   GET  /api/v1/configuration/device-features   -> DeviceFeaturesPage
 *   PUT  /api/v1/configuration/device-features   -> ConfigWriteAck   (autobackup only)
 *   GET  /api/v1/configuration/fault-detection   -> FaultDetectionPage
 *   PUT  /api/v1/configuration/fault-detection   -> ConfigWriteAck   (autobackup only)
 *   GET  /api/v1/configuration/monitor           -> MonitorPage
 *   PUT  /api/v1/configuration/monitor           -> ConfigWriteAck   (autobackup only)
 *   GET  /api/v1/configuration/bob-ports         -> BobPortsResponse
 *   PUT  /api/v1/configuration/bob-ports         -> ConfigWriteAck   (autobackup only)
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

export type PortConfig = components["schemas"]["PortConfig"];
export type PortConfigList = components["schemas"]["PortConfigList"];
export type PortForm = components["schemas"]["PortForm"];
export type PortMode = components["schemas"]["PortMode"];
export type SetPortConfigRequest =
  components["schemas"]["SetPortConfigRequest"];
export type SetPortConfigBody = components["schemas"]["SetPortConfigBody"];

export type DeviceFeaturesPage =
  components["schemas"]["DeviceFeaturesPage"];
export type SetDeviceFeaturesRequest =
  components["schemas"]["SetDeviceFeaturesRequest"];
export type SetDeviceFeaturesBody =
  components["schemas"]["SetDeviceFeaturesBody"];

export type FaultDetectionPage =
  components["schemas"]["FaultDetectionPage"];
export type FaultSensitivity =
  components["schemas"]["FaultSensitivity"];
export type SetFaultDetectionRequest =
  components["schemas"]["SetFaultDetectionRequest"];
export type SetFaultDetectionBody =
  components["schemas"]["SetFaultDetectionBody"];

export type MonitorPage = components["schemas"]["MonitorPage"];
export type SetMonitorRequest =
  components["schemas"]["SetMonitorRequest"];
export type SetMonitorBody = components["schemas"]["SetMonitorBody"];

export type BobPort = components["schemas"]["BobPort"];
export type BobDevice = components["schemas"]["BobDevice"];
export type BobPortsResponse =
  components["schemas"]["BobPortsResponse"];
export type SetBobPortsRequest =
  components["schemas"]["SetBobPortsRequest"];
export type SetBobPortsBody = components["schemas"]["SetBobPortsBody"];

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

// ---------------------------------------------------------------------------
// Ports (read list + per-port form)
// ---------------------------------------------------------------------------

export function usePortsConfig() {
  return useQuery<PortConfigList>({
    queryKey: ["configuration", "ports"],
    queryFn: () =>
      apiGet<PortConfigList>("/api/v1/configuration/ports"),
  });
}

export function usePortForm(port: number | null) {
  return useQuery<PortForm>({
    queryKey: ["configuration", "ports", port],
    queryFn: () =>
      apiGet<PortForm>(`/api/v1/configuration/ports/${port}`),
    enabled: port !== null && port > 0,
  });
}

export interface SetPortConfigArgs {
  port: number;
  body: SetPortConfigBody;
}

export function useSetPortConfig() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetPortConfigArgs>({
    mutationFn: ({ port, body }) =>
      apiPut<ConfigWriteAck, SetPortConfigBody>(
        `/api/v1/configuration/ports/${port}`,
        body,
      ),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: ["configuration", "ports"] });
      void qc.invalidateQueries({
        queryKey: ["configuration", "ports", variables.port],
      });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Device features
// ---------------------------------------------------------------------------

export function useDeviceFeatures() {
  return useQuery<DeviceFeaturesPage>({
    queryKey: ["configuration", "device-features"],
    queryFn: () =>
      apiGet<DeviceFeaturesPage>("/api/v1/configuration/device-features"),
  });
}

export function useSetDeviceFeatures() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetDeviceFeaturesBody>({
    mutationFn: (body) =>
      apiPut<ConfigWriteAck, SetDeviceFeaturesBody>(
        "/api/v1/configuration/device-features",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["configuration", "device-features"],
      });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Fault detection
// ---------------------------------------------------------------------------

export function useFaultDetection() {
  return useQuery<FaultDetectionPage>({
    queryKey: ["configuration", "fault-detection"],
    queryFn: () =>
      apiGet<FaultDetectionPage>("/api/v1/configuration/fault-detection"),
  });
}

export function useSetFaultDetection() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetFaultDetectionBody>({
    mutationFn: (body) =>
      apiPut<ConfigWriteAck, SetFaultDetectionBody>(
        "/api/v1/configuration/fault-detection",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["configuration", "fault-detection"],
      });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Monitor (port mirroring)
// ---------------------------------------------------------------------------

export function useMonitor() {
  return useQuery<MonitorPage>({
    queryKey: ["configuration", "monitor"],
    queryFn: () => apiGet<MonitorPage>("/api/v1/configuration/monitor"),
  });
}

export function useSetMonitor() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetMonitorBody>({
    mutationFn: (body) =>
      apiPut<ConfigWriteAck, SetMonitorBody>(
        "/api/v1/configuration/monitor",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["configuration", "monitor"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Bob-ports (device-view admin-status bulk toggle)
// ---------------------------------------------------------------------------

export function useBobPorts() {
  return useQuery<BobPortsResponse>({
    queryKey: ["configuration", "bob-ports"],
    queryFn: () =>
      apiGet<BobPortsResponse>("/api/v1/configuration/bob-ports"),
  });
}

export function useSetBobPorts() {
  const qc = useQueryClient();
  return useMutation<ConfigWriteAck, ApiError, SetBobPortsBody>({
    mutationFn: (body) =>
      apiPut<ConfigWriteAck, SetBobPortsBody>(
        "/api/v1/configuration/bob-ports",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["configuration", "bob-ports"] });
      // Admin-status changes also appear in the per-port config list.
      void qc.invalidateQueries({ queryKey: ["configuration", "ports"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}
