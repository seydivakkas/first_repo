import { artworkRepository } from '../artworks/artwork.repository';
import { eventRepository } from '../events/event.repository';

export const statsService = {
  summary() {
    return {
      totalArtworks: artworkRepository.list().length,
      totalEvents: eventRepository.list().length,
      revenueEstimate: 12000
    };
  },
  artworks() { return artworkRepository.list(); },
  events() { return eventRepository.list(); },
  revenue() { return { monthly: [{ month: 'Jan', amount: 5000 }, { month: 'Feb', amount: 7000 }] }; }
};
