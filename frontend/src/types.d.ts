declare namespace JSX {
  interface IntrinsicElements { [elemName: string]: any }
}

declare module 'react' {
  export const useState: any;
  export const useMemo: any;
  const React: any;
  export default React;
}

declare module 'react/jsx-runtime' {
  export const jsx: any;
  export const jsxs: any;
  export const Fragment: any;
}

declare module 'react-dom/client' { export const createRoot: any; }

declare module 'react-router-dom' {
  export const BrowserRouter: any;
  export const Routes: any;
  export const Route: any;
  export const Link: any;
  export const Navigate: any;
  export const useParams: any;
  export const useNavigate: any;
}

declare module 'recharts' {
  export const BarChart: any;
  export const Bar: any;
  export const XAxis: any;
  export const YAxis: any;
  export const Tooltip: any;
  export const ResponsiveContainer: any;
}
