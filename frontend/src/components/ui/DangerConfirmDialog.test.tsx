/**
 * Tests for the typed-confirmation gate that protects every lockout-risky
 * switch write (restore, device reset, IP change, passwords). If this
 * component regresses — confirm enabled without a match, or the typed value
 * surviving a reopen — a mis-click can reach fragile hardware.
 */
import { describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DangerConfirmDialog } from "./DangerConfirmDialog";

function renderDialog(props: Partial<Parameters<typeof DangerConfirmDialog>[0]> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  const utils = render(
    <DangerConfirmDialog
      open
      title="Restore backup"
      body={<p>body</p>}
      confirmationValue="192.0.2.3"
      confirmationLabel="Type the switch IP to confirm"
      confirmButtonText="Restore"
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onConfirm, onCancel, ...utils };
}

function confirmButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: "Restore" });
}

function confirmationInput(): HTMLInputElement {
  return screen.getByLabelText(/type the switch ip/i);
}

describe("DangerConfirmDialog", () => {
  it("keeps confirm disabled until the typed value matches exactly", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderDialog();

    expect(confirmButton()).toBeDisabled();

    await user.type(confirmationInput(), "192.0.2");
    expect(confirmButton()).toBeDisabled();

    await user.type(confirmationInput(), ".3");
    expect(confirmButton()).toBeEnabled();

    await user.click(confirmButton());
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("never enables confirm when confirmationValue is empty (identity not loaded)", async () => {
    const user = userEvent.setup();
    renderDialog({ confirmationValue: "" });
    await user.type(confirmationInput(), "anything");
    expect(confirmButton()).toBeDisabled();
  });

  it("resets the typed value when the dialog is reopened", async () => {
    const user = userEvent.setup();
    const { rerender } = renderDialog();

    await user.type(confirmationInput(), "192.0.2.3");
    expect(confirmButton()).toBeEnabled();

    // Close and reopen — the previous confirmation must NOT survive.
    rerender(
      <DangerConfirmDialog
        open={false}
        title="Restore backup"
        body={<p>body</p>}
        confirmationValue="192.0.2.3"
        confirmationLabel="Type the switch IP to confirm"
        confirmButtonText="Restore"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    rerender(
      <DangerConfirmDialog
        open
        title="Restore backup"
        body={<p>body</p>}
        confirmationValue="192.0.2.3"
        confirmationLabel="Type the switch IP to confirm"
        confirmButtonText="Restore"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(confirmationInput().value).toBe("");
    expect(confirmButton()).toBeDisabled();
    cleanup();
  });

  it("trims surrounding whitespace but not inner differences", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.type(confirmationInput(), "  192.0.2.3  ");
    expect(confirmButton()).toBeEnabled();
    cleanup();

    renderDialog();
    await user.type(confirmationInput(), "192.0.23");
    expect(confirmButton()).toBeDisabled();
  });

  it("locks cancel/Escape while busy so an in-flight write is not orphaned", async () => {
    const user = userEvent.setup();
    const { onCancel } = renderDialog({ busy: true });
    await user.keyboard("{Escape}");
    expect(onCancel).not.toHaveBeenCalled();
  });
});
