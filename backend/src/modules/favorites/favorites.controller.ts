import { Router } from 'express';
import { AuthRequest, authenticate, requireRole } from '../../middleware/auth.middleware';

const favoritesByUser: Record<string, string[]> = {};

export const favoritesRouter = Router();
favoritesRouter.use(authenticate, requireRole('user', 'admin'));
favoritesRouter.get('/favorites', (req: AuthRequest, res) => res.json(favoritesByUser[req.user!.id] || []));
favoritesRouter.post('/favorites', (req: AuthRequest, res) => {
  const favs = (favoritesByUser[req.user!.id] ||= []);
  if (!favs.includes(req.body.artworkId)) favs.push(req.body.artworkId);
  res.status(201).json(favs);
});
favoritesRouter.delete('/favorites/:id', (req: AuthRequest, res) => {
  favoritesByUser[req.user!.id] = (favoritesByUser[req.user!.id] || []).filter((id) => id !== req.params.id);
  res.json(favoritesByUser[req.user!.id]);
});
