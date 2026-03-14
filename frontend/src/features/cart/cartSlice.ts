export type CartItem = { id: string; title: string; price: number; qty: number };
export const addItem = (item: CartItem) => ({ type: 'cart/add', payload: item });
export const removeItem = (id: string) => ({ type: 'cart/remove', payload: id });
export const clearCart = () => ({ type: 'cart/clear' });

export default function cartReducer(state = { items: [] as CartItem[] }) {
  return state;
}
