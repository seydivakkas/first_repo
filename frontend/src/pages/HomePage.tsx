import { ArtworkCard } from '../components/ArtworkCard';
import { EventCard } from '../components/EventCard';
import { artworks, events } from '../data/mockData';

export default function HomePage() {
  return (
    <main className="mx-auto max-w-6xl p-6 space-y-8">
      <section className="rounded-3xl bg-gradient-to-r from-indigo-700 to-violet-700 p-8 text-white shadow-lg">
        <h1 className="text-4xl font-bold">Online Sanat Galerisi</h1>
        <p className="mt-3 max-w-2xl text-indigo-100">Premium sanat eserleri, özel etkinlikler ve koleksiyoner odaklı deneyim tek platformda.</p>
      </section>
      <section>
        <h2 className="text-2xl font-semibold">Öne Çıkan Eserler</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {artworks.slice(0, 3).map((a) => <ArtworkCard key={a.id} {...a} />)}
        </div>
      </section>
      <section>
        <h2 className="text-2xl font-semibold">Yaklaşan Etkinlikler</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {events.map((e) => <EventCard key={e.id} id={e.id} title={e.title} date={e.date} city={e.city} />)}
        </div>
      </section>
    </main>
  );
}
