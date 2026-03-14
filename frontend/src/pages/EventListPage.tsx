import { useMemo, useState } from 'react';
import { EventCard } from '../components/EventCard';
import { events } from '../data/mockData';

export default function EventListPage(){
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => events.filter((e) => `${e.title} ${e.city}`.toLowerCase().includes(query.toLowerCase())), [query]);
  return <div className="mx-auto max-w-6xl p-6"><h1 className="text-3xl font-bold mb-4">Etkinlikler</h1><input value={query} onChange={(e) => setQuery(e.target.value)} className="mb-4 w-full rounded-xl border p-3" placeholder="Etkinlik veya şehir ara"/><div className="grid gap-4 md:grid-cols-3">{filtered.map((e) => <EventCard key={e.id} id={e.id} title={e.title} date={e.date} city={e.city} />)}</div></div>
}
