import { Router } from 'express';
import { AuthRequest, authenticate, requireRole } from '../../middleware/auth.middleware';
import { reviewService } from './review.service';

export const reviewRouter = Router();
reviewRouter.get('/reviews', (req, res) => res.json(reviewService.list(req.query.targetId as string | undefined)));
reviewRouter.post('/reviews', authenticate, requireRole('user', 'admin'), (req: AuthRequest, res) => res.status(201).json(reviewService.create(req.body.targetId, req.user!.id, req.body.rating, req.body.comment)));
reviewRouter.post('/reviews/:id/vote', (req, res, next) => { try { res.json(reviewService.vote(req.params.id, req.body.up !== false)); } catch (e) { next(e); } });
reviewRouter.post('/reviews/:id/reply', (req, res, next) => { try { res.json(reviewService.reply(req.params.id, req.body.message)); } catch (e) { next(e); } });
