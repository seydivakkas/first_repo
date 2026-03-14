import { artworkRepository } from './artwork.repository';

export const artworkService = {
  list(search?: string) { return artworkRepository.list(search); },
  detail(id: string) { const a = artworkRepository.incrementView(id); if (!a) throw new Error('Artwork not found'); return a; },
  like(id: string) { const a = artworkRepository.toggleLike(id); if (!a) throw new Error('Artwork not found'); return a; },
  compare(ids: string[]) { return artworkRepository.compare(ids); }
};
