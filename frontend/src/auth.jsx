import { createContext, useContext } from "react";

const AuthContext = createContext(null);

export const AuthProvider = AuthContext.Provider;

export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used inside AuthProvider");
  return auth;
}
