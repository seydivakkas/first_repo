import { Router } from 'express';
import { AuthRequest, authenticate, requireRole } from '../../middleware/auth.middleware';
import { reservationService } from './reservation.service';

export const reservationRouter = Router();
reservationRouter.use(authenticate, requireRole('user', 'admin'));
reservationRouter.post('/reservations', (req: AuthRequest, res, next) => { try { res.status(201).json(reservationService.create(req.user!.id, req.body.eventId, req.body.participants, req.body.coupon)); } catch (e) { next(e); } });
reservationRouter.get('/reservations', (req: AuthRequest, res) => res.json(reservationService.list(req.user!.id)));
reservationRouter.patch('/reservations/:id/participants', (req, res, next) => { try { res.json(reservationService.updateParticipants(req.params.id, req.body.participants)); } catch (e) { next(e); } });
reservationRouter.delete('/reservations/:id', (req, res, next) => { try { res.json(reservationService.cancel(req.params.id)); } catch (e) { next(e); } });
