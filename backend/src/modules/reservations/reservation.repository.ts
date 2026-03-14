import { v4 as uuid } from 'uuid';

export type Reservation = { id: string; userId: string; eventId: string; participants: number; status: 'active' | 'cancelled'; total: number };
const reservations: Reservation[] = [];

export const reservationRepository = {
  create(userId: string, eventId: string, participants: number, total: number): Reservation {
    const r: Reservation = { id: uuid(), userId, eventId, participants, status: 'active', total };
    reservations.push(r);
    return r;
  },
  listByUser(userId: string) { return reservations.filter((r) => r.userId === userId); },
  updateParticipants(id: string, participants: number) { const r = reservations.find((x) => x.id === id); if (!r) return undefined; r.participants = participants; return r; },
  cancel(id: string) { const r = reservations.find((x) => x.id === id); if (!r) return undefined; r.status = 'cancelled'; return r; }
};
