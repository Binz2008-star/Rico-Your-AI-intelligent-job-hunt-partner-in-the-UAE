import { create } from 'zustand';
import { login as loginRequest, logout as logoutRequest } from '@/lib/api';
import { getExistingPublicUserId } from '@/lib/publicSession';

interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      // H-5 guest→account merge: if this browser holds a guest session, offer
      // it for merge. The backend decides — it requires the HttpOnly
      // `rico_guest_proof` capability cookie and a durable claim, so a stale or
      // foreign sid can never be merged, and an authenticated session is never
      // created on top of an unverified identity. No client-supplied id is
      // trusted as an ownership signal.
      const data = await loginRequest(email, password, getExistingPublicUserId());
      set({
        user: {
          id: data.email,
          email: data.email,
          name: data.email.split('@')[0],
        },
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },
  logout: async () => {
    await logoutRequest();
    set({ user: null, isAuthenticated: false });
  },
  setUser: (user) => {
    set({ user, isAuthenticated: !!user });
  },
}));
