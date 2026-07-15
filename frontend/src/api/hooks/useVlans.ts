/**
 * React Query hooks for the VLANs tab (Phase 4, F1).
 *
 * Backend endpoints:
 *   GET  /api/v1/vlans                  -> VlanList
 *   GET  /api/v1/vlans/{id}/ports       -> VlanMembershipList
 *   POST /api/v1/vlans                  -> VlanWriteAck (lockout-risky)
 *   POST /api/v1/vlans/delete           -> VlanWriteAck (lockout-risky)
 *   PUT  /api/v1/vlans/{id}/name        -> VlanWriteAck (lockout-risky)
 *   PUT  /api/v1/vlans/{id}/ports       -> VlanWriteAck (lockout-risky)
 *
 * No polling anywhere — VLAN state only changes when an operator changes
 * it, and the read-safety rule keeps switch cadence minimal. Mutations
 * invalidate ["vlans"] (fresh list + membership) and ["backups"] (the
 * pre-write autobackup is now on disk).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut, type ApiError } from "@/api/client";
import type { components } from "@/api/schema";

export type Vlan = components["schemas"]["Vlan"];
export type VlanList = components["schemas"]["VlanList"];
export type VlanMembership = components["schemas"]["VlanMembership"];
export type VlanMembershipList =
  components["schemas"]["VlanMembershipList"];
export type VlanWriteAck = components["schemas"]["VlanWriteAck"];

export type AddVlanBody = components["schemas"]["AddVlanBody"];
export type DelVlanBody = components["schemas"]["DelVlanBody"];
export type RenVlanBody = components["schemas"]["RenVlanBody"];
export type SetVlanPortsBody = components["schemas"]["SetVlanPortsBody"];
export type PortModeChange = components["schemas"]["PortModeChange"];

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

export function useVlans() {
  return useQuery<VlanList>({
    queryKey: ["vlans"],
    queryFn: () => apiGet<VlanList>("/api/v1/vlans"),
  });
}

export function useVlanPorts(vlanId: number | null) {
  return useQuery<VlanMembershipList>({
    queryKey: ["vlans", "ports", vlanId],
    queryFn: () =>
      apiGet<VlanMembershipList>(`/api/v1/vlans/${vlanId}/ports`),
    enabled: vlanId !== null,
  });
}

// ---------------------------------------------------------------------------
// Writes (all lockout-risky: confirm_switch_host + pre-write autobackup)
// ---------------------------------------------------------------------------

function useInvalidateVlans() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["vlans"] });
    void qc.invalidateQueries({ queryKey: ["backups"] });
  };
}

export function useAddVlan() {
  const invalidate = useInvalidateVlans();
  return useMutation<VlanWriteAck, ApiError, AddVlanBody>({
    mutationFn: (body) =>
      apiPost<VlanWriteAck, AddVlanBody>("/api/v1/vlans", body),
    onSuccess: invalidate,
  });
}

export function useDeleteVlans() {
  const invalidate = useInvalidateVlans();
  return useMutation<VlanWriteAck, ApiError, DelVlanBody>({
    mutationFn: (body) =>
      apiPost<VlanWriteAck, DelVlanBody>("/api/v1/vlans/delete", body),
    onSuccess: invalidate,
  });
}

export interface RenameVlanArgs {
  vlanId: number;
  body: RenVlanBody;
}

export function useRenameVlan() {
  const invalidate = useInvalidateVlans();
  return useMutation<VlanWriteAck, ApiError, RenameVlanArgs>({
    mutationFn: ({ vlanId, body }) =>
      apiPut<VlanWriteAck, RenVlanBody>(
        `/api/v1/vlans/${vlanId}/name`,
        body,
      ),
    onSuccess: invalidate,
  });
}

export interface SetVlanPortsArgs {
  vlanId: number;
  body: SetVlanPortsBody;
}

export function useSetVlanPorts() {
  const invalidate = useInvalidateVlans();
  return useMutation<VlanWriteAck, ApiError, SetVlanPortsArgs>({
    mutationFn: ({ vlanId, body }) =>
      apiPut<VlanWriteAck, SetVlanPortsBody>(
        `/api/v1/vlans/${vlanId}/ports`,
        body,
      ),
    onSuccess: invalidate,
  });
}
