import { Router } from 'express';
import Joi from 'joi';
import { authenticate, AuthRequest, requireRole } from '../../middleware/auth.middleware';
import { validate } from '../../middleware/validate.middleware';
import { authService } from './auth.service';

export const authRouter = Router();

authRouter.post('/register', validate(Joi.object({ email: Joi.string().email().required(), password: Joi.string().min(6).required(), name: Joi.string().required() })), async (req, res, next) => {
  try { res.status(201).json(await authService.register(req.body.email, req.body.password, req.body.name)); } catch (e) { next(e); }
});
authRouter.post('/login', validate(Joi.object({ email: Joi.string().email().required(), password: Joi.string().required() })), async (req, res, next) => {
  try { res.json(await authService.login(req.body.email, req.body.password)); } catch (e) { next(e); }
});
authRouter.get('/profile', authenticate, requireRole('user', 'admin'), (req: AuthRequest, res, next) => {
  try { res.json(authService.getProfile(req.user!.id)); } catch (e) { next(e); }
});
authRouter.patch('/profile', authenticate, requireRole('user', 'admin'), async (req: AuthRequest, res, next) => {
  try {
    if (req.body.currentPassword && req.body.newPassword) {
      res.json(await authService.changePassword(req.user!.id, req.body.currentPassword, req.body.newPassword));
      return;
    }
    res.json(await authService.updateProfile(req.user!.id, req.body.name));
  } catch (e) { next(e); }
});
