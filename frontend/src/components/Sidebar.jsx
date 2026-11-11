import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

const ICONS = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>
  ),
  detection: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2.5" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
  ),
  video: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2.5" y="5" width="14" height="14" rx="2" /><path d="M16.5 10l5-3v10l-5-3" /></svg>
  ),
  tracking: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20c4 0 3-6 7-6s3 6 7 6" /><circle cx="4" cy="20" r="1.6" /><circle cx="18" cy="4" r="1.6" /><path d="M4 20c8 0 2-12 14-12" strokeDasharray="3 2.4" /></svg>
  ),
  lane: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 21L11 3M16 21L13 3" /><path d="M12 7v2M12 12v2M12 17v2" strokeDasharray="none" /></svg>
  ),
  depth: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 13l9 5 9-5" opacity="0.65" /><path d="M3 17.5l9 5 9-5" opacity="0.35" /></svg>
  ),
  simulation: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 15l1.7-5.2A2.5 2.5 0 018.1 8h7.8a2.5 2.5 0 012.4 1.8L20 15v4h-2.2M4 15v4h2.2M4 15h16" /><circle cx="8" cy="17.5" r="1.8" /><circle cx="16" cy="17.5" r="1.8" /></svg>
  ),
  doubts: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" /><path d="M9.5 9h.01M14.5 9h.01M9 13.5c1 1 5 1 6 0" /></svg>
  ),
};

const NAV = [
  { to: '/', label: 'Home Dashboard', icon: 'dashboard' },
  { to: '/detection', label: 'Object Detection', icon: 'detection' },
  { to: '/video-analysis', label: 'Video Analysis', icon: 'video' },
  { to: '/tracking', label: 'Object Tracking', icon: 'tracking' },
  { to: '/lane-detection', label: 'Lane Detection', icon: 'lane' },
  { to: '/depth-estimation', label: 'Depth Estimation', icon: 'depth' },
  { to: '/simulation', label: 'Driving Simulation', icon: 'simulation' },
  { to: '/doubts', label: 'Doubts Assistant', icon: 'doubts' },
];

export default function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand">
        <div className="brand-logo" aria-hidden="true">
          <svg viewBox="0 0 64 64"><path d="M14 38c2-8 6-12 18-12s16 4 18 12v6H14z" fill="currentColor" /><circle cx="21" cy="46" r="5" fill="none" stroke="currentColor" strokeWidth="3" /><circle cx="43" cy="46" r="5" fill="none" stroke="currentColor" strokeWidth="3" /></svg>
        </div>
        <div className="brand-text">
          <span className="brand-name">ADAS</span>
          <span className="brand-sub">Autonomous Driving AI</span>
        </div>
        <button type="button" className="sidebar-close" onClick={onClose} aria-label="Close menu">✕</button>
      </div>

      <nav className="nav">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <span className="nav-icon" aria-hidden="true">{ICONS[item.icon]}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {user && (
        <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border-soft)', background: 'rgba(9, 15, 29, 0.6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#93c5fd' }}>
              👤 {user.user_id}
            </span>
            <button
              type="button"
              onClick={logout}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#f87171',
                fontSize: '11px',
                cursor: 'pointer',
                padding: '2px 6px',
              }}
            >
              Sign Out
            </button>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block' }}>
            {user.email || 'Authenticated Driver'}
          </span>
        </div>
      )}

      <div className="sidebar-foot">
        <span className="foot-dot" aria-hidden="true" />
        YOLO · ByteTrack · OpenCV · MiDaS
      </div>
    </aside>
  );
}
