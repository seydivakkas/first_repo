import { v4 as uuid } from 'uuid';

type Order = { id: string; userId: string; items: Array<{ id: string; qty: number; price: number }>; total: number; status: 'pending' | 'paid' };
const orders: Order[] = [];

export const orderService = {
  create(userId: string, items: Array<{ id: string; qty: number; price: number }>) {
    const total = items.reduce((sum, i) => sum + i.qty * i.price, 0);
    const order: Order = { id: uuid(), userId, items, total, status: 'pending' };
    orders.push(order);
    return order;
  },
  list(userId: string) { return orders.filter((o) => o.userId === userId); },
  markPaid(id: string) { const o = orders.find((x) => x.id === id); if (!o) throw new Error('Order not found'); o.status = 'paid'; return o; }
};
