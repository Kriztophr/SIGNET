import {
  Boxes,
  ClipboardCheck,
  Gauge,
  HeartPulse,
  Home,
  LogOut,
  Rocket,
  Workflow as WorkflowIcon,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

const NAV = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/workflows", label: "Workflows", icon: WorkflowIcon },
  { to: "/runs", label: "Runs", icon: Boxes },
  { to: "/reviews", label: "Reviews", icon: ClipboardCheck },
  { to: "/evals", label: "Evals", icon: Gauge },
  { to: "/promotions", label: "Promotions", icon: Rocket },
  { to: "/resilience", label: "Resilience", icon: HeartPulse },
];

export function Layout() {
  const { user, logout } = useAuth();
  const initial = (user?.full_name ?? "?").trim().charAt(0).toUpperCase();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="logo" title="ICM Console">
          <WorkflowIcon size={22} strokeWidth={2.2} />
        </div>
        <nav>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} title={label} aria-label={label}>
              <Icon size={20} strokeWidth={2} />
            </NavLink>
          ))}
        </nav>
        <div className="spacer" />
        <button className="icon-button" onClick={logout} title="Sign out" aria-label="Sign out">
          <LogOut size={19} />
        </button>
      </aside>
      <main className="content">
        <div className="topbar">
          <div className="whoami">
            <div className="avatar">{initial}</div>
            <div className="who-text">
              <strong>{user?.full_name}</strong>
              <span>{user?.role.replaceAll("_", " ")}</span>
            </div>
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
