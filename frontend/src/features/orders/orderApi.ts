export const orderApi = { reducerPath: 'orderApi', reducer: () => ({}), middleware: () => (next: any) => (action: any) => next(action) };
export const useGetOrdersQuery = () => ({ data: [] as any[], isLoading: false });
