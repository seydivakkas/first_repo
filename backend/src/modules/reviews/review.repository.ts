import { v4 as uuid } from 'uuid';

type Review = { id: string; targetId: string; userId: string; rating: number; comment: string; votes: number; replies: string[] };
const reviews: Review[] = [];

export const reviewRepository = {
  create(targetId: string, userId: string, rating: number, comment: string) {
    const review: Review = { id: uuid(), targetId, userId, rating, comment, votes: 0, replies: [] };
    reviews.push(review);
    return review;
  },
  list(targetId?: string) { return reviews.filter((r) => !targetId || r.targetId === targetId); },
  vote(id: string, delta: number) { const r = reviews.find((x) => x.id === id); if (!r) return undefined; r.votes += delta; return r; },
  reply(id: string, message: string) { const r = reviews.find((x) => x.id === id); if (!r) return undefined; r.replies.push(message); return r; }
};
