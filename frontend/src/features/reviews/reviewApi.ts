export const reviewApi = { reducerPath: 'reviewApi', reducer: () => ({}), middleware: () => (next: any) => (action: any) => next(action) };
export const useGetReviewsQuery = (_targetId: string) => ({ data: { data: [], breakdown: {} }, isLoading: false });
