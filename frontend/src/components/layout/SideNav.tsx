import { Link } from "@tanstack/react-router";

/**
 * Navigation target shown in the left sidebar. `to` values mirror the
 * TanStack Router paths generated from the file-based routes.
 */
type NavItem = {
  readonly to: string;
  readonly label: string;
};

const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Identity" },
  { to: "/status", label: "Status" },
  { to: "/configuration", label: "Configuration" },
  { to: "/security", label: "Security" },
  { to: "/diagnostics", label: "Diagnostics" },
  { to: "/support", label: "Support" },
  { to: "/backups", label: "Backups" },
];

export function SideNav() {
  return (
    <nav className="sticky top-14 h-[calc(100vh-3.5rem)] w-60 shrink-0 border-r border-border bg-muted p-3">
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              // Identity lives at "/" which would match as a prefix for every
              // route; restrict its active styling to exact matches so other
              // tabs don't also render as active.
              activeOptions={item.to === "/" ? { exact: true } : undefined}
              className="block rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              activeProps={{
                className:
                  "block rounded-md px-3 py-2 text-sm bg-primary text-primary-foreground",
              }}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
