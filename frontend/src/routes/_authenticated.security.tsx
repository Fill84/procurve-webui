import { createFileRoute } from "@tanstack/react-router";
import { ComingLaterPage } from "@/features/coming-later/ComingLaterPage";

export const Route = createFileRoute("/_authenticated/security")({
  component: () => <ComingLaterPage tabName="Security" />,
});
