export const reservationApi = { reducerPath: 'reservationApi', reducer: () => ({}), middleware: () => (next: any) => (action: any) => next(action) };
export const useGetReservationsQuery = () => ({ data: [] as any[], isLoading: false });
