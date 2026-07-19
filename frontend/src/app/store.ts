export type RootState = {
  auth: { token: string | null; email: string | null };
  cart: { items: Array<{ id: string; title: string; price: number; qty: number }> };
  ui: { toast: string };
};

export const store = {
  getState: (): RootState => ({ auth: { token: null, email: null }, cart: { items: [] }, ui: { toast: '' } }),
  dispatch: (_action: unknown) => _action
};

export type AppDispatch = typeof store.dispatch;
