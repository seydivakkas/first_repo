import { Router } from 'express';
import { eventService } from './event.service';

export const eventRouter = Router();
eventRouter.get('/events', (req, res) => res.json(eventService.list(req.query.search as string | undefined)));
eventRouter.get('/events/compare', (req, res) => res.json(eventService.compare(String(req.query.ids || '').split(',').filter(Boolean))));
eventRouter.get('/events/:id', (req, res, next) => { try { res.json(eventService.detail(req.params.id)); } catch (e) { next(e); } });
