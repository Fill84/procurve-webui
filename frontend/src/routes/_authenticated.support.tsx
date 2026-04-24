import { createFileRoute } from "@tanstack/react-router";
import { SupportPage } from "@/features/support/SupportPage";

export const Route = createFileRoute("/_authenticated/support")({
  component: SupportPage,
});
