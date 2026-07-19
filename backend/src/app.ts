import cors from 'cors';
import express from 'express';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import { env } from './config/env';
import { errorHandler } from './middleware/error.middleware';
import { adminRouter } from './modules/admin/admin.controller';
import { artworkRouter } from './modules/artworks/artwork.controller';
import { authRouter } from './modules/auth/auth.controller';
import { eventRouter } from './modules/events/event.controller';
import { favoritesRouter } from './modules/favorites/favorites.controller';
import { orderRouter } from './modules/orders/order.controller';
import { reservationRouter } from './modules/reservations/reservation.controller';
import { reviewRouter } from './modules/reviews/review.controller';
import { supportRouter } from './modules/support/support.controller';

export const app = express();
app.use(helmet());
app.use(cors({ origin: env.frontendOrigin }));
app.use(express.json());
app.use(rateLimit({ windowMs: 60 * 1000, max: 120 }));

app.get('/health', (_req, res) => res.json({ ok: true }));
app.use('/api', authRouter, artworkRouter, eventRouter, reservationRouter, orderRouter, reviewRouter, supportRouter, favoritesRouter, adminRouter);
app.use(errorHandler);
