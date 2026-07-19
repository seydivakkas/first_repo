import { useState } from 'react';

export const ReservationForm = () => {
  const [participants, setParticipants] = useState(1);
  const [coupon, setCoupon] = useState('');
  const total = participants * 100 * (coupon === 'GALERI10' ? 0.9 : 1);

  return <form className="rounded-2xl border bg-white p-4 shadow-sm"><h3 className="font-bold mb-3">Rezervasyon Oluştur</h3><label className="text-sm">Katılımcı Sayısı</label><input type="number" min={1} value={participants} onChange={(e) => setParticipants(Number(e.target.value || 1))} className="mt-1 mb-3 w-full rounded-lg border p-2"/><label className="text-sm">Kupon Kodu</label><input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="GALERI10" className="mt-1 mb-3 w-full rounded-lg border p-2"/><p className="mb-3 text-sm">Toplam: <strong>₺{total.toFixed(0)}</strong></p><button type="button" className="rounded-lg bg-indigo-600 px-4 py-2 text-white">Rezerve Et</button></form>;
};
