import { useMemo, useState } from 'react';
import { ArtworkCard } from '../components/ArtworkCard';
import { artworks } from '../data/mockData';

export default function ArtworkListPage() {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => artworks.filter((a) => `${a.title} ${a.artist} ${a.category}`.toLowerCase().includes(query.toLowerCase())), [query]);

  return <div className="mx-auto max-w-6xl p-6"><h1 className="text-3xl font-bold mb-4">Eserler</h1><input value={query} onChange={(e) => setQuery(e.target.value)} className="mb-4 w-full rounded-xl border p-3" placeholder="Sanatçı, eser veya kategori ara"/><div className="grid gap-4 md:grid-cols-3">{filtered.map((a) => <ArtworkCard key={a.id} {...a} />)}</div></div>;
}
