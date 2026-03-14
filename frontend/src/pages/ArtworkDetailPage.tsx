import { useParams } from 'react-router-dom';
import { ReviewSection } from '../components/ReviewSection';
import { artworks } from '../data/mockData';

export default function ArtworkDetailPage(){
  const { id } = useParams();
  const artwork = artworks.find((a) => a.id === id) || artworks[0];
  return <div className="mx-auto max-w-5xl p-6"><div className="grid gap-6 md:grid-cols-2"><img src={artwork.image} alt={artwork.title} className="h-80 w-full rounded-2xl object-cover"/><div><p className="text-sm text-indigo-600">{artwork.category}</p><h1 className="text-3xl font-bold">{artwork.title}</h1><p className="mt-1 text-slate-600">{artwork.artist}</p><p className="mt-4">{artwork.description}</p><p className="mt-6 text-2xl font-bold">₺{artwork.price.toLocaleString('tr-TR')}</p></div></div><ReviewSection/></div>
}
