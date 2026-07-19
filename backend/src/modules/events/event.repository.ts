export type Event = { id: string; title: string; date: string; capacity: number; reserved: number; views: number };
const events: Event[] = [
  { id: 'e1', title: 'Modern Art Night', date: '2026-01-01', capacity: 100, reserved: 10, views: 0 },
  { id: 'e2', title: 'Renaissance Workshop', date: '2026-02-15', capacity: 30, reserved: 5, views: 0 }
];

export const eventRepository = {
  list(search?: string) { return events.filter((e) => !search || e.title.toLowerCase().includes(search.toLowerCase())); },
  getById(id: string) { return events.find((e) => e.id === id); },
  incrementView(id: string) { const e = events.find((x) => x.id === id); if (e) e.views += 1; return e; },
  compare(ids: string[]) { return events.filter((e) => ids.includes(e.id)); }
};
