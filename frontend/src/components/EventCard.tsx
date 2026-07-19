import { Link } from 'react-router-dom';

export const EventCard = ({ id, title, date, city }: any) => (
  <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
    <p className="text-xs uppercase tracking-wide text-emerald-600">{city}</p>
    <h3 className="text-lg font-semibold mt-1">{title}</h3>
    <p className="text-sm text-slate-600 mt-1">{date}</p>
    <Link to={`/events/${id}`} className="inline-block mt-3 text-sm font-medium text-indigo-600 hover:underline">Detay</Link>
  </article>
);
