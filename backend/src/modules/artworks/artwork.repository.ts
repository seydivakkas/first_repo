export type Artwork = { id: string; title: string; artist: string; category: string; likes: number; views: number };
const artworks: Artwork[] = [
  { id: 'a1', title: 'Yıldızlı Gece', artist: 'Van Gogh', category: 'Post-Impressionism', likes: 0, views: 0 },
  { id: 'a2', title: 'Mona Lisa', artist: 'Da Vinci', category: 'Renaissance', likes: 0, views: 0 }
];

export const artworkRepository = {
  list(search?: string) { return artworks.filter((a) => !search || `${a.title} ${a.artist}`.toLowerCase().includes(search.toLowerCase())); },
  getById(id: string) { return artworks.find((a) => a.id === id); },
  toggleLike(id: string) { const a = artworks.find((x) => x.id === id); if (!a) return undefined; a.likes += 1; return a; },
  incrementView(id: string) { const a = artworks.find((x) => x.id === id); if (a) a.views += 1; return a; },
  compare(ids: string[]) { return artworks.filter((a) => ids.includes(a.id)); }
};
