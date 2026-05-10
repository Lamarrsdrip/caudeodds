import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, tokenStore, formatApiError } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const t = tokenStore.get();
    if (!t) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      tokenStore.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = async (email, password) => {
    const res = await api.login({ email, password });
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const register = async (payload) => {
    const res = await api.register(payload);
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const logout = async () => {
    try { await api.logout(); } catch {}
    tokenStore.clear();
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, refresh, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
export { formatApiError };
