/**
 * React Query hooks for the Security tab (Task 3.4).
 *
 * Backend endpoints:
 *   GET  /api/v1/security/web-access              -> WebAccessPage
 *   GET  /api/v1/security/web-managers            -> WebManagersResponse
 *   GET  /api/v1/security/per-port                -> PerportsResponse
 *   GET  /api/v1/security/intrusion               -> IntrusionLogResponse
 *   GET  /api/v1/security/ssl-state               -> SSLState
 *   PUT  /api/v1/security/web-access              -> SetSSLResponse (lockout-risky)
 *   POST /api/v1/security/web-managers            -> SetWebManagerResponse (lockout-risky)
 *   PUT  /api/v1/security/device-passwords        -> SetDevicePasswordsResponse (lockout-risky)
 *   PUT  /api/v1/security/per-port/{port}         -> SetPerportResponse
 *   POST /api/v1/security/intrusion/reset         -> ResetIntrusionFlagsResponse
 *
 * Every mutation invalidates:
 *   1. Its own resource query (so the UI refetches the fresh state), and
 *   2. ["backups"]  (the pre-write autobackup is now on disk — the Backups
 *      tab should show it next time the user opens it).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut, type ApiError } from "@/api/client";
import type { components } from "@/api/schema";

export type WebAccessPage = components["schemas"]["WebAccessPage"];
export type WebManagersResponse =
  components["schemas"]["WebManagersResponse"];
export type PerportsResponse = components["schemas"]["PerportsResponse"];
export type IntrusionLogResponse =
  components["schemas"]["IntrusionLogResponse"];
export type SSLState = components["schemas"]["SSLState"];

export type SetSSLBody = components["schemas"]["SetSSLBody"];
export type SetSSLRequest = components["schemas"]["SetSSLRequest"];
export type SetSSLResponse = components["schemas"]["SetSSLResponse"];

export type SetWebManagerBody = components["schemas"]["SetWebManagerBody"];
export type SetWebManagerResponse =
  components["schemas"]["SetWebManagerResponse"];
export type AddWebManagerRequest =
  components["schemas"]["AddWebManagerRequest"];
export type ReplaceWebManagerRequest =
  components["schemas"]["ReplaceWebManagerRequest"];
export type DeleteWebManagerRequest =
  components["schemas"]["DeleteWebManagerRequest"];

export type SetDevicePasswordsBody =
  components["schemas"]["SetDevicePasswordsBody"];
export type SetDevicePasswordsRequest =
  components["schemas"]["SetDevicePasswordsRequest"];
export type SetDevicePasswordsResponse =
  components["schemas"]["SetDevicePasswordsResponse"];

export type SetPerportBody = components["schemas"]["SetPerportBody"];
export type SetPerportRequest = components["schemas"]["SetPerportRequest"];
export type SetPerportResponse = components["schemas"]["SetPerportResponse"];
export type ResetIntrusionFlagsResponse =
  components["schemas"]["ResetIntrusionFlagsResponse"];
export type AuthorizedManager = components["schemas"]["AuthorizedManager"];
export type PortSecurityRow = components["schemas"]["PortSecurityRow"];
export type IntrusionEntry = components["schemas"]["IntrusionEntry"];

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

export function useWebAccess() {
  return useQuery<WebAccessPage>({
    queryKey: ["security", "web-access"],
    queryFn: () => apiGet<WebAccessPage>("/api/v1/security/web-access"),
  });
}

export function useWebManagers() {
  return useQuery<WebManagersResponse>({
    queryKey: ["security", "web-managers"],
    queryFn: () =>
      apiGet<WebManagersResponse>("/api/v1/security/web-managers"),
  });
}

export function usePerPort(group: string = "") {
  return useQuery<PerportsResponse>({
    queryKey: ["security", "per-port", group],
    queryFn: () =>
      apiGet<PerportsResponse>(
        `/api/v1/security/per-port${group ? `?group=${encodeURIComponent(group)}` : ""}`,
      ),
  });
}

export function useIntrusion() {
  return useQuery<IntrusionLogResponse>({
    queryKey: ["security", "intrusion"],
    queryFn: () =>
      apiGet<IntrusionLogResponse>("/api/v1/security/intrusion"),
  });
}

export function useSslState() {
  return useQuery<SSLState>({
    queryKey: ["security", "ssl-state"],
    queryFn: () => apiGet<SSLState>("/api/v1/security/ssl-state"),
  });
}

// ---------------------------------------------------------------------------
// Writes
// ---------------------------------------------------------------------------

export function useSetWebAccess() {
  const qc = useQueryClient();
  return useMutation<SetSSLResponse, ApiError, SetSSLBody>({
    mutationFn: (body) =>
      apiPut<SetSSLResponse, SetSSLBody>(
        "/api/v1/security/web-access",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["security", "web-access"] });
      void qc.invalidateQueries({ queryKey: ["security", "ssl-state"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

export function useSetWebManager() {
  const qc = useQueryClient();
  return useMutation<SetWebManagerResponse, ApiError, SetWebManagerBody>({
    mutationFn: (body) =>
      apiPost<SetWebManagerResponse, SetWebManagerBody>(
        "/api/v1/security/web-managers",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["security", "web-managers"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

export function useSetDevicePasswords() {
  const qc = useQueryClient();
  return useMutation<
    SetDevicePasswordsResponse,
    ApiError,
    SetDevicePasswordsBody
  >({
    mutationFn: (body) =>
      apiPut<SetDevicePasswordsResponse, SetDevicePasswordsBody>(
        "/api/v1/security/device-passwords",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["security", "web-access"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

export interface SetPerportArgs {
  port: number;
  body: SetPerportBody;
}

export function useSetPerport() {
  const qc = useQueryClient();
  return useMutation<SetPerportResponse, ApiError, SetPerportArgs>({
    mutationFn: ({ port, body }) =>
      apiPut<SetPerportResponse, SetPerportBody>(
        `/api/v1/security/per-port/${port}`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["security", "per-port"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}

export function useResetIntrusion() {
  const qc = useQueryClient();
  return useMutation<ResetIntrusionFlagsResponse, ApiError, void>({
    mutationFn: () =>
      apiPost<ResetIntrusionFlagsResponse, undefined>(
        "/api/v1/security/intrusion/reset",
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["security", "intrusion"] });
      void qc.invalidateQueries({ queryKey: ["backups"] });
    },
  });
}
