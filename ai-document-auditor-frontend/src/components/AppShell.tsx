import { Link, NavLink, Outlet } from "react-router-dom";

export default function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="sidebar-brand" title="Back to the landing page">
          <span className="sidebar-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M6 3.5h9l4.5 4.5v12.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"
                stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"
              />
              <path d="M15 3.5V8h4.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
              <path d="M8.5 13.5l2.4 2.4 4.6-4.9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="sidebar-brand-name">Document Auditor</span>
        </Link>

        <nav className="sidebar-nav">
          <NavLink to="/dashboard" className={({ isActive }) => `sidebar-nav-item ${isActive ? "sidebar-nav-item-active" : ""}`}>
            <span className="sidebar-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3.5" y="3.5" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
                <rect x="13.5" y="3.5" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
                <rect x="3.5" y="13.5" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
                <rect x="13.5" y="13.5" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="1.6" />
              </svg>
            </span>
            Dashboard
          </NavLink>
          <NavLink to="/new" className={({ isActive }) => `sidebar-nav-item ${isActive ? "sidebar-nav-item-active" : ""}`}>
            <span className="sidebar-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </span>
            New Audit
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          Hybrid BM25 + vector retrieval, guardrail-verified citations.
        </div>
      </aside>

      <div className="app-content">
        <Outlet />
      </div>
    </div>
  );
}
