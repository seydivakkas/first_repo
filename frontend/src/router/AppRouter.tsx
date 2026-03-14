import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { ProtectedRoute } from '../components/ProtectedRoute';
import AdminDashboard from '../pages/AdminDashboard';
import ArtworkDetailPage from '../pages/ArtworkDetailPage';
import ArtworkListPage from '../pages/ArtworkListPage';
import ComparePage from '../pages/ComparePage';
import EventDetailPage from '../pages/EventDetailPage';
import EventListPage from '../pages/EventListPage';
import HomePage from '../pages/HomePage';
import LoginPage from '../pages/LoginPage';
import OrderPage from '../pages/OrderPage';
import ProfilePage from '../pages/ProfilePage';
import RegisterPage from '../pages/RegisterPage';
import ReservationPage from '../pages/ReservationPage';
import SupportPage from '../pages/SupportPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/artworks" element={<ArtworkListPage />} />
        <Route path="/artworks/:id" element={<ArtworkDetailPage />} />
        <Route path="/events" element={<EventListPage />} />
        <Route path="/events/:id" element={<EventDetailPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/reservations" element={<ProtectedRoute><ReservationPage /></ProtectedRoute>} />
        <Route path="/orders" element={<ProtectedRoute><OrderPage /></ProtectedRoute>} />
        <Route path="/support" element={<ProtectedRoute><SupportPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminDashboard /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
