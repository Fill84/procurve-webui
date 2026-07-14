/**
 * SystemInfoCard — edit SNMP system name / location / contact.
 *
 * Not lockout-risky: these fields are cosmetic SNMP strings. No
 * confirmation dialog — the write goes straight through on Save.
 * A pre-write autobackup is still taken server-side, so the operator
 * can roll back from the Backups tab if they change their mind.
 *
 * The MAC address is also scraped from system.html; we show it as a
 * read-only row so the operator has a one-glance confirmation of which
 * switch they're editing.
 */
import { useEffect, useState } from "react";
import {
  useSetSystemInfo,
  useSystemInfo,
  type SetSystemInfoRequest,
} from "@/api/hooks/useConfiguration";

// Char whitelist mirrored from the backend SYSTEM_FIELD_PATTERN. Printable
// ASCII minus `~`. We don't validate client-side beyond non-empty name:
// if the user types a `~` the backend rejects with a 422 we surface as-is.
const MAX_NAME = 30;
const MAX_TEXT = 48;

export function SystemInfoCard() {
  const query = useSystemInfo();
  const mutation = useSetSystemInfo();

  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [contact, setContact] = useState("");
  const [lastResult, setLastResult] = useState<string | null>(null);

  // Seed local form state from the fetched page the first time it arrives.
  useEffect(() => {
    if (query.data) {
      setName(query.data.name);
      setLocation(query.data.location);
      setContact(query.data.contact);
    }
  }, [query.data]);

  const handleSave = () => {
    setLastResult(null);
    mutation.reset();
    const request: SetSystemInfoRequest = {
      name: name.trim(),
      location,
      contact,
    };
    mutation.mutate(
      { request },
      {
        onSuccess: (data) => {
          setLastResult(
            data.ok ? "System info saved." : "Save accepted without confirmation.",
          );
        },
      },
    );
  };

  const errorMessage =
    mutation.error instanceof Error ? mutation.error.message : null;

  const dirty =
    !!query.data &&
    (name !== query.data.name ||
      location !== query.data.location ||
      contact !== query.data.contact);

  const canSave = !mutation.isPending && dirty && name.trim().length > 0;

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          System info
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.isLoading && (
        <div className="grid gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded border border-border bg-muted"
            />
          ))}
        </div>
      )}

      {query.error instanceof Error && (
        <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
          <p className="font-medium">Failed to load system info</p>
          <p className="mt-1 break-all">{query.error.message}</p>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="mt-2 rounded-md border border-red-400 dark:border-red-900 bg-card px-3 py-1.5 text-sm font-medium text-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
          >
            Retry
          </button>
        </div>
      )}

      {query.data && (
        <>
          <dl className="mb-4 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 text-sm">
            <dt className="text-muted-foreground">MAC address</dt>
            <dd className="font-mono text-foreground">
              {query.data.mac_address}
            </dd>
          </dl>

          <div className="grid gap-3">
            <div>
              <label
                htmlFor="sys-name"
                className="block text-xs font-medium text-foreground"
              >
                System name
              </label>
              <input
                id="sys-name"
                type="text"
                value={name}
                maxLength={MAX_NAME}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="sys-location"
                className="block text-xs font-medium text-foreground"
              >
                Location
              </label>
              <input
                id="sys-location"
                type="text"
                value={location}
                maxLength={MAX_TEXT}
                onChange={(e) => setLocation(e.target.value)}
                className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="sys-contact"
                className="block text-xs font-medium text-foreground"
              >
                Contact
              </label>
              <input
                id="sys-contact"
                type="text"
                value={contact}
                maxLength={MAX_TEXT}
                onChange={(e) => setContact(e.target.value)}
                className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={!canSave}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {mutation.isPending ? "Saving…" : "Save"}
            </button>
            {dirty && !mutation.isPending && (
              <button
                type="button"
                onClick={() => {
                  if (!query.data) return;
                  setName(query.data.name);
                  setLocation(query.data.location);
                  setContact(query.data.contact);
                  setLastResult(null);
                  mutation.reset();
                }}
                className="text-sm text-muted-foreground hover:text-foreground hover:underline"
              >
                Revert
              </button>
            )}
            {lastResult && (
              <span className="text-sm italic text-foreground">
                {lastResult}
              </span>
            )}
          </div>

          {errorMessage && (
            <div className="mt-3 rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
              <p className="font-semibold">Save failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
