import { eventRepository } from '../events/event.repository';
import { reservationRepository } from './reservation.repository';

export const reservationService = {
  create(userId: string, eventId: string, participants: number, coupon?: string) {
    const event = eventRepository.getById(eventId);
    if (!event) throw new Error('Event not found');
    // Simulated SELECT FOR UPDATE lock: single-threaded in-memory mutation
    if (event.capacity - event.reserved < participants) throw new Error('Not enough capacity');
    event.reserved += participants;
    const base = participants * 100;
    const discount = coupon === 'GALERI10' ? base * 0.1 : 0;
    return reservationRepository.create(userId, eventId, participants, base - discount);
  },
  list(userId: string) { return reservationRepository.listByUser(userId); },
  updateParticipants(id: string, participants: number) { const r = reservationRepository.updateParticipants(id, participants); if (!r) throw new Error('Reservation not found'); return r; },
  cancel(id: string) { const r = reservationRepository.cancel(id); if (!r) throw new Error('Reservation not found'); return r; }
};
