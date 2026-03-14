import { Router } from 'express';
import { authenticate, requireRole } from '../../middleware/auth.middleware';
import { statsService } from './stats.service';

export const adminRouter = Router();
adminRouter.use(authenticate, requireRole('admin'));
adminRouter.get('/admin/summary', (_req, res) => res.json(statsService.summary()));
adminRouter.get('/admin/artworks', (_req, res) => res.json(statsService.artworks()));
adminRouter.get('/admin/events', (_req, res) => res.json(statsService.events()));
adminRouter.get('/admin/revenue', (_req, res) => res.json(statsService.revenue()));
