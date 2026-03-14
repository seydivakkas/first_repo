import { Router } from 'express';
import { AuthRequest, authenticate, requireRole } from '../../middleware/auth.middleware';
import { supportService } from './support.service';

export const supportRouter = Router();
supportRouter.use(authenticate, requireRole('user', 'admin'));
supportRouter.post('/support', (req: AuthRequest, res) => res.status(201).json(supportService.create(req.user!.id, req.body.subject, req.body.message)));
supportRouter.get('/support', (req: AuthRequest, res) => res.json(supportService.list(req.user!.id)));
supportRouter.post('/support/:id/messages', (req, res, next) => { try { res.json(supportService.addMessage(req.params.id, req.body.message)); } catch (e) { next(e); } });
