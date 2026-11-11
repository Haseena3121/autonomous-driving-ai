import { useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

export default function LoginPage() {
  const { login, register, loading } = useAuth();
  const [isRegistering, setIsRegistering] = useState(false);
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    try {
      if (isRegistering) {
        await register(userId, password, name, email);
      } else {
        await login(userId, password);
      }
    } catch (err) {
      setError(err);
    }
  };

  const fillDemo = () => {
    setUserId('demo');
    setPassword('demo123');
    setIsRegistering(false);
    setError(null);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        background:
          'radial-gradient(1000px 500px at 50% 0%, rgba(59, 130, 246, 0.15), transparent 70%), #070b14',
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '440px',
          padding: '36px 32px',
          borderRadius: '18px',
          border: '1px solid rgba(59, 130, 246, 0.25)',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.55)',
          background: 'rgba(13, 21, 38, 0.95)',
          backdropFilter: 'blur(12px)',
        }}
      >
        {/* Brand header */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div
            style={{
              width: '60px',
              height: '60px',
              margin: '0 auto 14px',
              background: 'linear-gradient(135deg, #1d4ed8, #38bdf8)',
              borderRadius: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 24px rgba(56, 189, 248, 0.35)',
            }}
          >
            <svg viewBox="0 0 64 64" width="36" height="36" fill="#ffffff">
              <path d="M14 38c2-8 6-12 18-12s16 4 18 12v6H14z" />
              <circle cx="21" cy="46" r="5" fill="none" stroke="#ffffff" strokeWidth="3" />
              <circle cx="43" cy="46" r="5" fill="none" stroke="#ffffff" strokeWidth="3" />
            </svg>
          </div>
          <h1 style={{ margin: '0 0 6px 0', fontSize: '24px', letterSpacing: '0.5px' }}>
            ADAS Autonomous Driving AI
          </h1>
          <p className="muted" style={{ margin: '0 0 10px 0', fontSize: '13px' }}>
            {isRegistering
              ? 'Create your User ID to access the perception dashboard'
              : 'Sign in to access perception models and simulation'}
          </p>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <span
              className="chip chip-post"
              style={{ fontSize: '11px', padding: '3px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
            >
              🍃 Database: MongoDB (Connected)
            </span>
          </div>
        </div>

        {/* Tab switch */}
        <div
          style={{
            display: 'flex',
            background: '#090f1d',
            borderRadius: '10px',
            padding: '4px',
            marginBottom: '22px',
            border: '1px solid #1a2744',
          }}
        >
          <button
            type="button"
            className="btn"
            style={{
              flex: 1,
              padding: '8px 12px',
              fontSize: '13px',
              background: !isRegistering ? 'var(--accent-grad)' : 'transparent',
              color: !isRegistering ? '#061020' : 'var(--muted)',
              border: 'none',
              fontWeight: !isRegistering ? '600' : 'normal',
            }}
            onClick={() => {
              setIsRegistering(false);
              setError(null);
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            className="btn"
            style={{
              flex: 1,
              padding: '8px 12px',
              fontSize: '13px',
              background: isRegistering ? 'var(--accent-grad)' : 'transparent',
              color: isRegistering ? '#061020' : 'var(--muted)',
              border: 'none',
              fontWeight: isRegistering ? '600' : 'normal',
            }}
            onClick={() => {
              setIsRegistering(true);
              setError(null);
            }}
          >
            Create User ID
          </button>
        </div>

        <ErrorAlert error={error} title="Authentication Error" />

        {successMsg && (
          <div className="alert alert-ok" style={{ marginBottom: '18px' }}>
            {successMsg}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <label className="field" style={{ minWidth: 'auto' }}>
            <span style={{ fontSize: '13px' }}>User ID</span>
            <input
              type="text"
              required
              placeholder="e.g. haseena, engineer1, admin"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              disabled={loading}
              autoFocus
            />
          </label>

          {isRegistering && (
            <>
              <label className="field" style={{ minWidth: 'auto' }}>
                <span style={{ fontSize: '13px' }}>Full Name (Optional)</span>
                <input
                  type="text"
                  placeholder="e.g. Alex Rivera"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                />
              </label>

              <label className="field" style={{ minWidth: 'auto' }}>
                <span style={{ fontSize: '13px' }}>Email Address (Optional)</span>
                <input
                  type="email"
                  placeholder="e.g. driver@autonomous.ai"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                />
              </label>
            </>
          )}

          <label className="field" style={{ minWidth: 'auto' }}>
            <span style={{ fontSize: '13px' }}>Password</span>
            <input
              type="password"
              required
              placeholder="Enter password (min 4 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
            />
          </label>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !userId.trim() || !password.trim()}
            style={{ width: '100%', padding: '12px', marginTop: '8px', fontSize: '15px' }}
          >
            {loading ? 'Please wait…' : isRegistering ? '✨ Create User ID & Sign In' : '➔ Sign In'}
          </button>
        </form>

        {/* Quick demo helper */}
        <div
          style={{
            marginTop: '22px',
            paddingTop: '18px',
            borderTop: '1px solid #16243f',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            alignItems: 'center',
          }}
        >
          <span style={{ fontSize: '12px', color: '#94a3b8' }}>
            Quick test with pre-configured demo account:
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={fillDemo}
            style={{ fontSize: '12px', padding: '6px 14px' }}
          >
            🔑 Fill Demo (User: <strong style={{ color: '#93c5fd' }}>demo</strong> / Pass: <strong style={{ color: '#93c5fd' }}>demo123</strong>)
          </button>
        </div>
      </div>
    </div>
  );
}
