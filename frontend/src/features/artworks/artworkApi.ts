export const artworkApi = { reducerPath: 'artworkApi', reducer: () => ({}), middleware: () => (next: any) => (action: any) => next(action) };
export const useGetArtworksQuery = () => ({ data: [] as any[], isLoading: false });
export const useGetArtworkQuery = (_id: string) => ({ data: null as any, isLoading: false });
