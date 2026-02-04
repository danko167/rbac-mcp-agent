import { createContext } from "react";

export type Me = {
  id: number;
  email: string;
  roles: string[];
  permissions: string[];
};

export type AuthContextType = {
  token: string | null;
  isReady: boolean;

  me: Me | null;
  meLoading: boolean;
  meError: string | null;
  refreshMe: () => Promise<void>;

  login: (token: string) => void;
  logout: () => void;
};

export const AuthContext = createContext<AuthContextType | null>(null);
