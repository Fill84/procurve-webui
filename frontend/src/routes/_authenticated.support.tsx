import { createFileRoute } from "@tanstack/react-router";
import { ComingLaterPage } from "@/features/coming-later/ComingLaterPage";

export const Route = createFileRoute("/_authenticated/support")({
  component: () => <ComingLaterPage tabName="Support" />,
});
