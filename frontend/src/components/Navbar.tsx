import { Link } from 'react-router-dom';

const items = [
  ['/', 'Home'],
  ['/artworks', 'Artworks'],
  ['/events', 'Events'],
  ['/compare', 'Compare'],
  ['/reservations', 'Reservations'],
  ['/orders', 'Orders'],
  ['/support', 'Support'],
  ['/admin', 'Admin']
];

export const Navbar = () => (
  <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
    <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3">
      <Link className="mr-2 text-lg font-bold text-indigo-700" to="/">Online Sanat Galerisi</Link>
      {items.map(([to, label]) => (
        <Link key={to} to={to} className="rounded-lg px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100">{label}</Link>
      ))}
      <div className="ml-auto flex gap-2">
        <Link to="/login" className="rounded-lg border px-3 py-1.5 text-sm">Login</Link>
        <Link to="/register" className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white">Register</Link>
      </div>
    </nav>
  </header>
);
