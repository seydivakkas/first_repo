import { Link } from 'react-router-dom';

export const ArtworkCard = ({ id, title, artist, category, price, image }: any) => (
  <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md transition">
    <img className="h-48 w-full object-cover" src={image} alt={title} />
    <div className="p-4 space-y-1">
      <p className="text-xs uppercase tracking-wide text-indigo-600">{category}</p>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-slate-600">{artist}</p>
      <div className="flex items-center justify-between pt-2">
        <span className="font-bold">₺{price.toLocaleString('tr-TR')}</span>
        <Link to={`/artworks/${id}`} className="text-sm font-medium text-indigo-600 hover:underline">Detay</Link>
      </div>
    </div>
  </article>
);
