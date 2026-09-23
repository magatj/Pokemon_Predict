import { NavLink, type NavLinkRenderProps } from "react-router-dom";

import { PokeballMark } from "./PokeballMark";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Sidebar shell around every page.
 *
 * The nav only lists destinations that exist. A "Map", "Alerts" or "Settings"
 * entry that goes nowhere looks like a feature and is really just a dead link,
 * so those are left out until they do something.
 */

interface NavItem {
  to: string;
  label: string;
  icon: JSX.Element;
}

const NAV: NavItem[] = [
  {
    to: "/",
    label: "Dashboard",
    icon: (
      <path d="M3 10.5 12 3l9 7.5M5.25 9.75V20a1 1 0 0 0 1 1h3.5v-5.5h4.5V21h3.5a1 1 0 0 0 1-1V9.75" />
    ),
  },
  {
    to: "/sources",
    label: "Sources",
    icon: (
      <>
        <path d="M4 7c0-1.66 3.58-3 8-3s8 1.34 8 3-3.58 3-8 3-8-1.34-8-3Z" />
        <path d="M4 7v10c0 1.66 3.58 3 8 3s8-1.34 8-3V7" />
        <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
      </>
    ),
  },
  {
    to: "/about",
    label: "How it works",
    icon: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 16v-4M12 8.5h.01" />
      </>
    ),
  },
];

function navClass({ isActive }: NavLinkRenderProps): string {
  return `nav__item ${isActive ? "nav__item--active" : ""}`;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="sidebar">
        <div className="brand">
          <PokeballMark className="brand__mark" />
          <div className="brand__text">
            <span className="brand__name">Vending</span>
            <span className="brand__name brand__name--accent">Forecast</span>
          </div>
        </div>

        <nav className="nav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"} className={navClass}>
              <svg
                className="nav__icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                {item.icon}
              </svg>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__foot">
          <ThemeToggle />
          <p className="sidebar__tagline">
            Community data.
            <br />
            Better odds for everyone.
          </p>
          <p className="sidebar__version">v0.1.0 · MVP</p>
        </div>
      </aside>

      <main className="main" id="main">
        {children}
      </main>
    </div>
  );
}
