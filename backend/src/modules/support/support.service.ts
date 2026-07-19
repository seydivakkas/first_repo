import { v4 as uuid } from 'uuid';

type Ticket = { id: string; userId: string; subject: string; messages: string[] };
const tickets: Ticket[] = [];

export const supportService = {
  create(userId: string, subject: string, message: string) {
    const ticket: Ticket = { id: uuid(), userId, subject, messages: [message] };
    tickets.push(ticket);
    return ticket;
  },
  list(userId: string) { return tickets.filter((t) => t.userId === userId); },
  addMessage(id: string, message: string) { const t = tickets.find((x) => x.id === id); if (!t) throw new Error('Ticket not found'); t.messages.push(message); return t; }
};
