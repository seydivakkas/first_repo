export type Artwork = { id: string; title: string; artist: string; category: string; price: number; image: string; description: string };
export type Event = { id: string; title: string; date: string; city: string; capacity: number; description: string };

export const artworks: Artwork[] = [
  { id: 'a1', title: 'Yıldızlı Gece', artist: 'Van Gogh', category: 'Post-Impressionism', price: 7800, image: 'https://images.unsplash.com/photo-1579783901586-d88db74b4fe4?w=800', description: 'Yoğun fırça dokusu ve dramatik gökyüzüyle ikonik eser.' },
  { id: 'a2', title: 'Mona Lisa', artist: 'Da Vinci', category: 'Renaissance', price: 12500, image: 'https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?w=800', description: 'Rönesans portre sanatının en bilinen örneklerinden biri.' },
  { id: 'a3', title: 'Soyut Harmoni', artist: 'Aylin Demir', category: 'Contemporary', price: 3400, image: 'https://images.unsplash.com/photo-1545239351-1141bd82e8a6?w=800', description: 'Renk bloklarıyla modern denge ve ritim arayışı.' }
];

export const events: Event[] = [
  { id: 'e1', title: 'Modern Art Night', date: '2026-01-01', city: 'İstanbul', capacity: 100, description: 'Canlı müzik eşliğinde çağdaş eser sunumu.' },
  { id: 'e2', title: 'Renaissance Workshop', date: '2026-02-15', city: 'Ankara', capacity: 30, description: 'Klasik çizim teknikleri uygulamalı atölye.' },
  { id: 'e3', title: 'Collector Meetup', date: '2026-03-10', city: 'İzmir', capacity: 60, description: 'Koleksiyonerler için ağ ve danışmanlık günü.' }
];
