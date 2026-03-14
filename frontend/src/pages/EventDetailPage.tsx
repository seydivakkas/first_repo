import { useParams } from 'react-router-dom';
import { ReservationForm } from '../components/ReservationForm';
import { events } from '../data/mockData';

export default function EventDetailPage(){
  const { id } = useParams();
  const event = events.find((e) => e.id === id) || events[0];
  return <div className="mx-auto max-w-4xl p-6 space-y-4"><h1 className="text-3xl font-bold">{event.title}</h1><p className="text-slate-600">{event.city} • {event.date}</p><p>{event.description}</p><ReservationForm/></div>
}
