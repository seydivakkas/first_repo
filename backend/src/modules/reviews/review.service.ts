import { reviewRepository } from './review.repository';

export const reviewService = {
  list(targetId?: string) {
    const data = reviewRepository.list(targetId);
    const breakdown = data.reduce<Record<number, number>>((acc, r) => ((acc[r.rating] = (acc[r.rating] || 0) + 1), acc), {});
    return { data, breakdown };
  },
  create(targetId: string, userId: string, rating: number, comment: string) { return reviewRepository.create(targetId, userId, rating, comment); },
  vote(id: string, up = true) { const r = reviewRepository.vote(id, up ? 1 : -1); if (!r) throw new Error('Review not found'); return r; },
  reply(id: string, message: string) { const r = reviewRepository.reply(id, message); if (!r) throw new Error('Review not found'); return r; }
};
