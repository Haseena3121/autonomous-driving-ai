import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('adas_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      localStorage.setItem('adas_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('adas_user');
    }
  }, [user]);

  const login = async (userId, password) => {
    setLoading(true);
    try {
      const res = await api.login(userId, password);
      setUser(res.user);
      return res;
    } finally {
      setLoading(false);
    }
  };

  const register = async (userId, password, name, email) => {
    setLoading(true);
    try {
      const res = await api.register(userId, password, name, email);
      setUser(res.user);
      return res;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('adas_user');
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: Boolean(user), login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
