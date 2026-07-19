import { Router } from 'express';
import { artworkService } from './artwork.service';

export const artworkRouter = Router();
artworkRouter.get('/artworks', (req, res) => res.json(artworkService.list(req.query.search as string | undefined)));
artworkRouter.get('/artworks/compare', (req, res) => res.json(artworkService.compare(String(req.query.ids || '').split(',').filter(Boolean))));
artworkRouter.get('/artworks/:id', (req, res, next) => { try { res.json(artworkService.detail(req.params.id)); } catch (e) { next(e); } });
artworkRouter.post('/artworks/:id/like', (req, res, next) => { try { res.json(artworkService.like(req.params.id)); } catch (e) { next(e); } });
