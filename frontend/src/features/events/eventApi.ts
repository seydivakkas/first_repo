export const eventApi = { reducerPath: 'eventApi', reducer: () => ({}), middleware: () => (next: any) => (action: any) => next(action) };
export const useGetEventsQuery = () => ({ data: [] as any[], isLoading: false });
export const useGetEventQuery = (_id: string) => ({ data: null as any, isLoading: false });
