/**
 * DevicePasswordsCard — change Operator and Manager credentials.
 *
 * LOCKOUT RISK (worst of the three lockout-risky writes): a wrong Manager
 * password — or a non-matching confirm — locks every client out of the
 * switch with no software path back. Recovery is physical factory-reset
 * only. We surface this loudly and gate the submit through the shared
 * DangerConfirmDialog with the switch IP as the friction value, matching
 * WebAccessCard / WebManagersCard.
 *
 * The 2810 firmware also sends the new password CLEARTEXT in the URL
 * query string. We mirror that on the wire (a protocol-level flaw, not
 * fixable client-side) and warn the user up-front so they can pick the
 * right link / proxy.
 *
 * The legacy applet (mirrored screenshot) renders two sections: Read-Only
 * Access (Operator) and Read-Write Access (Manager). We follow the same
 * grouping so muscle memory carries over.
 */
import { useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { useIdentity } from "@/api/hooks/useIdentity";
import { useSetDevicePasswords } from "@/api/hooks/useSecurity";

interface FormState {
  operator_username: string;
  operator_password: string;
  operator_password_confirm: string;
  manager_username: string;
  manager_password: string;
  manager_password_confirm: string;
}

const EMPTY_FORM: FormState = {
  operator_username: "",
  operator_password: "",
  operator_password_confirm: "",
  manager_username: "",
  manager_password: "",
  manager_password_confirm: "",
};

export function DevicePasswordsCard() {
  const identity = useIdentity();
  const setPasswords = useSetDevicePasswords();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const expectedIp = identity.data?.ip_address ?? "";

  const update = <K extends keyof FormState>(key: K, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  // Local validation: confirm fields must match their primary; Manager
  // fields are required (Manager creds are the only path back into the
  // switch). Operator section is optional — empty fields are a no-op for
  // that pair, mirroring the legacy applet's behaviour.
  const operatorConfirmMismatch =
    form.operator_password !== form.operator_password_confirm;
  const managerConfirmMismatch =
    form.manager_password !== form.manager_password_confirm;
  const managerEmpty =
    form.manager_username.trim() === "" || form.manager_password === "";

  const canSubmit =
    !operatorConfirmMismatch &&
    !managerConfirmMismatch &&
    !managerEmpty &&
    !!expectedIp &&
    !setPasswords.isPending;

  const handleApply = () => {
    setLastResult(null);
    setPasswords.reset();
    setDialogOpen(true);
  };

  const handleClear = () => {
    setForm(EMPTY_FORM);
    setLastResult(null);
    setPasswords.reset();
  };

  const handleConfirm = () => {
    if (!expectedIp) return;
    setPasswords.mutate(
      {
        request: {
          operator_username: form.operator_username,
          operator_password: form.operator_password,
          operator_password_confirm: form.operator_password_confirm,
          manager_username: form.manager_username,
          manager_password: form.manager_password,
          manager_password_confirm: form.manager_password_confirm,
        },
        confirm_switch_host: expectedIp,
      },
      {
        onSuccess: (data) => {
          setDialogOpen(false);
          setForm(EMPTY_FORM);
          setLastResult(
            data.applied
              ? "Passwords applied. The next request will use the new credentials — sign in again if prompted."
              : (data.message ?? "Request accepted."),
          );
        },
      },
    );
  };

  const errorMessage =
    setPasswords.error instanceof Error ? setPasswords.error.message : null;

  const dialogBody = (
    <div className="space-y-3">
      <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
        <p className="font-semibold">Physical-recovery lockout risk</p>
        <p className="mt-1">
          A wrong Manager password — or a non-matching confirm — locks every
          client out of this switch. There is no software path back: recovery
          requires a physical factory-reset (clear button on the chassis).
          Make sure you have console / SSH access ready before applying.
        </p>
      </div>
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-semibold">Cleartext-on-the-wire warning</p>
        <p className="mt-1">
          The 2810 firmware sends the new password as a query-string
          parameter on a plain HTTP GET. The bytes leave this container in
          the clear unless you are tunnelling through HTTPS / a VPN. Pick
          the right link before applying.
        </p>
      </div>
      <div className="rounded border border-neutral-200 bg-neutral-50 p-3 text-sm">
        <p>
          <span className="font-semibold">Operator:</span>{" "}
          {form.operator_username.trim() === "" && form.operator_password === ""
            ? "(unchanged)"
            : `username "${form.operator_username}" + new password`}
        </p>
        <p className="mt-1">
          <span className="font-semibold">Manager:</span>{" "}
          {`username "${form.manager_username}" + new password`}
        </p>
      </div>
    </div>
  );

  const confirmationHint = (
    <>
      Expected:{" "}
      {expectedIp ? (
        <span className="font-mono text-neutral-700">{expectedIp}</span>
      ) : (
        <span className="italic">loading identity…</span>
      )}
    </>
  );

  return (
    <>
      <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
            Device passwords
          </h4>
        </div>

        <div className="mb-4 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-semibold">Physical-recovery lockout</p>
          <p className="mt-1">
            A wrong Manager password locks the switch. Recovery is the
            physical reset button on the chassis — there is no software
            override.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Read-Only Access (Operator) */}
          <fieldset className="rounded border border-neutral-200 p-4">
            <legend className="px-2 text-xs font-semibold uppercase tracking-wide text-neutral-600">
              Read-Only Access (Operator)
            </legend>
            <div className="space-y-3">
              <PwField
                id="op-username"
                label="Operator user name"
                type="text"
                value={form.operator_username}
                onChange={(v) => update("operator_username", v)}
                autoComplete="off"
              />
              <PwField
                id="op-pw"
                label="Operator password"
                type="password"
                value={form.operator_password}
                onChange={(v) => update("operator_password", v)}
                autoComplete="new-password"
              />
              <PwField
                id="op-pw2"
                label="Confirm operator password"
                type="password"
                value={form.operator_password_confirm}
                onChange={(v) => update("operator_password_confirm", v)}
                autoComplete="new-password"
                error={
                  operatorConfirmMismatch
                    ? "Does not match the operator password."
                    : undefined
                }
              />
            </div>
          </fieldset>

          {/* Read-Write Access (Manager) */}
          <fieldset className="rounded border border-neutral-200 p-4">
            <legend className="px-2 text-xs font-semibold uppercase tracking-wide text-neutral-600">
              Read-Write Access (Manager)
            </legend>
            <div className="space-y-3">
              <PwField
                id="mgr-username"
                label="Manager user name"
                type="text"
                value={form.manager_username}
                onChange={(v) => update("manager_username", v)}
                autoComplete="off"
              />
              <PwField
                id="mgr-pw"
                label="Manager password"
                type="password"
                value={form.manager_password}
                onChange={(v) => update("manager_password", v)}
                autoComplete="new-password"
              />
              <PwField
                id="mgr-pw2"
                label="Confirm manager password"
                type="password"
                value={form.manager_password_confirm}
                onChange={(v) => update("manager_password_confirm", v)}
                autoComplete="new-password"
                error={
                  managerConfirmMismatch
                    ? "Does not match the manager password."
                    : undefined
                }
              />
            </div>
          </fieldset>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={handleClear}
            disabled={setPasswords.isPending}
            className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            Clear changes
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={!canSubmit}
            className="rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
          >
            Apply changes (dangerous)…
          </button>
        </div>

        {lastResult && (
          <p className="mt-3 text-sm italic text-neutral-700">{lastResult}</p>
        )}
      </section>

      <DangerConfirmDialog
        open={dialogOpen}
        title="Apply device-password change"
        body={dialogBody}
        confirmationValue={expectedIp}
        confirmationLabel="Type the switch IP to confirm"
        confirmationHint={confirmationHint}
        confirmationPlaceholder="e.g. 192.168.1.10"
        confirmButtonText="Apply password change"
        busyButtonText="Applying…"
        onConfirm={handleConfirm}
        onCancel={() => setDialogOpen(false)}
        busy={setPasswords.isPending}
        error={
          errorMessage ? (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              <p className="font-semibold">Apply failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          ) : null
        }
      />
    </>
  );
}

interface PwFieldProps {
  id: string;
  label: string;
  type: "text" | "password";
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  error?: string;
}

function PwField({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  error,
}: PwFieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-xs font-medium text-neutral-700"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        spellCheck={false}
        className={`mt-1 w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 ${
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-500"
            : "border-neutral-300 focus:border-blue-500 focus:ring-blue-500"
        }`}
      />
      {error && <p className="mt-1 text-xs text-red-700">{error}</p>}
    </div>
  );
}
