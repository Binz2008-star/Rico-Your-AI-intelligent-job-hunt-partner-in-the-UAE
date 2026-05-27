import { authApi as ricoAuthApi } from './client';
import type { LoginResponse, RegisterResponse } from '@/lib/schemas';

export interface LoginCredentials {
  email: string;
  password: string;
  public_user_id_to_merge?: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  name?: string;
  public_user_id_to_merge?: string;
}

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    return ricoAuthApi.login(credentials);
  },

  logout: async (): Promise<void> => {
    await ricoAuthApi.logout();
  },

  register: async (data: RegisterPayload): Promise<RegisterResponse & { email_verification_required?: boolean }> => {
    return ricoAuthApi.register({
      email: data.email,
      password: data.password,
      role: 'user',
      public_user_id_to_merge: data.public_user_id_to_merge,
    });
  },
};
