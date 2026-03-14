const reviews = [
  { user: 'Mert', rating: 5, text: 'Eser kalitesi ve kargolama harika.' },
  { user: 'Deniz', rating: 4, text: 'Etkinlik çok keyifliydi, tekrar katılırım.' }
];

export const ReviewSection = () => <section className="mt-6 rounded-2xl border bg-white p-4 shadow-sm"><h3 className="mb-3 text-lg font-semibold">Yorumlar</h3><div className="space-y-3">{reviews.map((r) => <article key={r.user + r.text} className="rounded-lg border p-3"><p className="text-sm font-medium">{r.user} • {'★'.repeat(r.rating)}</p><p className="text-sm text-slate-600 mt-1">{r.text}</p></article>)}</div></section>;
