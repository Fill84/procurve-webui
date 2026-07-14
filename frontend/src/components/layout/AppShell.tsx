import { Outlet } from "@tanstack/react-router";
import { TopBar } from "./TopBar";
import { SideNav } from "./SideNav";

/**
 * Two-column authenticated layout: sticky TopBar spanning the full width,
 * sticky SideNav on the left, and the routed page content on the right.
 */
export function AppShell() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <TopBar />
      <div className="flex">
        <SideNav />
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
