import { Link, NavLink, useMatch, type NavLinkRenderProps } from "react-router-dom";

import { ThemeToggle } from "./ThemeToggle";
import { icons } from "./icons";

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
  const machineDetailPage = useMatch("/machine/:machineId");
  const machinesTab = useMatch("/machines");
  const machinePage = machineDetailPage || machinesTab;
  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="sidebar">
        <Link className="brand" to="/" aria-label="Pokémon Vending Tracker home">
          <span className="brand__pokemon">Pokémon</span>
          <span className="brand__subtitle">Vending Tracker</span>
          <span className="brand__community">COMMUNITY POWERED</span>
        </Link>

        <nav className="nav" aria-label="Primary">
          {NAV.slice(0, 1).map((item) => (
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
          <NavLink
            className={({ isActive }) => `nav__item ${isActive || machinePage ? "nav__item--active" : ""}`}
            to="/machines"
          >
            <span className="nav__icon" aria-hidden="true">{icons.pin}</span>
            <span>Machines</span>
          </NavLink>
          {machinePage && (
            <>
              <a className="nav__item" href="#location">
                <span className="nav__icon" aria-hidden="true">{icons.pin}</span>
                <span>Location</span>
              </a>
              <a className="nav__item" href="#reports">
                <span className="nav__icon" aria-hidden="true">{icons.doc}</span>
                <span>Reports</span>
              </a>
            </>
          )}
          {NAV.slice(1).map((item) => (
            <NavLink key={item.to} to={item.to} className={navClass}>
              <svg className="nav__icon" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"
                strokeLinejoin="round" aria-hidden="true">{item.icon}</svg>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__foot">
          <p className="sidebar__tagline">
            Stronger together
            <br />
            for the hunt!
          </p>
          <span className="decorative-pokeball" aria-hidden="true" />
          <ThemeToggle />
          <p className="sidebar__version">v0.1.0 · MVP</p>
        </div>
      </aside>

      <main className="main" id="main">
        {children}
      </main>
    </div>
  );
}
