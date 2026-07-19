import { eventRepository } from './event.repository';

export const eventService = {
  list(search?: string) { return eventRepository.list(search); },
  detail(id: string) { const e = eventRepository.incrementView(id); if (!e) throw new Error('Event not found'); return e; },
  compare(ids: string[]) { return eventRepository.compare(ids); }
};
