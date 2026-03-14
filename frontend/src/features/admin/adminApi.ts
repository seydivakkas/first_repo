export const adminApi = { reducerPath: 'adminApi', reducer: () => ({}), middleware: () => (next: any) => (action: any) => next(action) };
export const useGetSummaryQuery = () => ({ data: { totalArtworks: 2, totalEvents: 2, revenueEstimate: 12000 }, isLoading: false });
export const useGetRevenueQuery = () => ({ data: { monthly: [{ month: 'Jan', amount: 5000 }] }, isLoading: false });
