import { useEffect, useState } from 'react';
import { api } from '../services/api.js';
import { useAuth } from '../context/AuthContext.jsx';
import StatusBadge from './StatusBadge.jsx';

/** Top bar: page title + live backend/model status pill + user info + logout. */
export default function TopBar({ title, subtitle, onToggleMenu }) {
  const [health, setHealth] = useState(null);
  const { user, logout } = useAuth();

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await api.getHealth();
        if (alive) setHealth(data);
      } catch {
        if (alive) setHealth(null);
      }
    };
    load();
    const timer = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const model = health?.model;
  const apiOnline = Boolean(health);

  return (
    <div className="topbar">
      <button type="button" className="menu-btn" onClick={onToggleMenu} aria-label="Open menu">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="22" height="22"><path d="M3 6h18M3 12h18M3 18h18" /></svg>
      </button>
      <div className="topbar-titles">
        <h2>{title}</h2>
        {subtitle ? <span className="topbar-sub">{subtitle}</span> : null}
      </div>
      <div className="topbar-status">
        <span className={`status-pill ${apiOnline ? 'pill-online' : 'pill-offline'}`}>
          <span className="pill-dot" aria-hidden="true" />
          API {apiOnline ? 'online' : 'offline'}
        </span>
        {model ? (
          <span className="status-pill pill-model">
            Model:&nbsp;<StatusBadge status={model.status === 'missing' ? 'standby' : model.status} label={model.status === 'loaded' ? `Loaded · ${(model.device || 'cpu').toUpperCase()}` : 'Ready'} />
          </span>
        ) : null}

        {/* User profile badge & Logout button */}
        {user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '6px' }}>
            <span
              className="chip"
              style={{
                background: 'rgba(56, 189, 248, 0.12)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                padding: '4px 10px',
                fontSize: '12px',
              }}
            >
              👤 {user.name || user.user_id}
            </span>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={logout}
              title="Sign out of ADAS Dashboard"
              style={{
                fontSize: '12px',
                padding: '4px 10px',
                borderColor: 'rgba(239, 68, 68, 0.35)',
                color: '#fca5a5',
              }}
            >
              🚪 Logout
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
