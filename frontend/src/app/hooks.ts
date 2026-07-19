import type { AppDispatch, RootState } from './store';

export const useAppDispatch = (): AppDispatch => ((action: unknown) => action) as AppDispatch;
export const useAppSelector = <TSelected>(selector: (state: RootState) => TSelected): TSelected =>
  selector({ auth: { token: null, email: null }, cart: { items: [] }, ui: { toast: '' } });
