import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

const NAV = [
  { to: "/reviews", label: "Reviews" },
  { to: "/evals", label: "Evals" },
  { to: "/runs", label: "Runs" },
  { to: "/promotions", label: "Promotions" },
  { to: "/resilience", label: "Resilience" },
];

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          ICM <span>Console</span>
        </div>
        <nav>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="whoami">
            <strong>{user?.full_name}</strong>
            <span className="muted">{user?.role.replaceAll("_", " ")}</span>
          </div>
          <button className="ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
