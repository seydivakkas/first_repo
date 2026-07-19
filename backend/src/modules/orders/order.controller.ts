import { Router } from 'express';
import { AuthRequest, authenticate, requireRole } from '../../middleware/auth.middleware';
import { orderService } from './order.service';
import { paymentService } from './payment.service';

export const orderRouter = Router();
orderRouter.use(authenticate, requireRole('user', 'admin'));
orderRouter.post('/orders', (req: AuthRequest, res) => res.status(201).json(orderService.create(req.user!.id, req.body.items || [])));
orderRouter.get('/orders', (req: AuthRequest, res) => res.json(orderService.list(req.user!.id)));
orderRouter.post('/orders/:id/pay', (req, res, next) => { try { res.json(paymentService.pay(req.params.id, req.body.gatewayToken)); } catch (e) { next(e); } });
