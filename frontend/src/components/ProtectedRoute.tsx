import { Navigate } from 'react-router-dom';

export const ProtectedRoute = ({ children }: { children: any }) => {
  const token = globalThis.localStorage?.getItem('token');
  return token ? children : <Navigate to="/login" replace />;
};
