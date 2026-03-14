export type AuthState = { token: string | null; email: string | null; loading: boolean };
export const initialAuthState: AuthState = { token: null, email: null, loading: false };

export const login = async (payload: { email: string; password: string }) => ({ token: 'mock-token', email: payload.email });
export const register = async (payload: { email: string; password: string }) => ({ token: 'mock-token', email: payload.email });
export const profile = async () => ({ email: 'demo@gallery.com' });
export const logout = () => ({ type: 'auth/logout' });

export default function authReducer(state = initialAuthState): AuthState {
  return state;
}
