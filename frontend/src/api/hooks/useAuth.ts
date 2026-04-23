import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, ApiError } from "@/api/client";
import type { components } from "@/api/schema";

type Whoami = components["schemas"]["WhoamiResponse"];
type LoginRequest = components["schemas"]["LoginRequest"];
type LoginResponse = components["schemas"]["LoginResponse"];

/**
 * Query the current session. Returns `null` on 401 (unauthenticated) so
 * consumers — especially the TanStack Router `beforeLoad` guard — can branch
 * on absence without catching an exception at their call site.
 */
export function useWhoami() {
  return useQuery<Whoami | null>({
    queryKey: ["whoami"],
    queryFn: async () => {
      try {
        return await apiGet<Whoami>("/api/v1/auth/whoami");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation<LoginResponse, ApiError, LoginRequest>({
    mutationFn: (body) =>
      apiPost<LoginResponse, LoginRequest>("/api/v1/auth/login", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["whoami"] });
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation<void, ApiError>({
    mutationFn: () => apiPost<void>("/api/v1/auth/logout"),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["whoami"] });
    },
  });
}
