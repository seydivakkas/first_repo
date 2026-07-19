declare module 'express' {
  export interface Request { [key: string]: any }
  export interface Response { [key: string]: any }
  export interface NextFunction { (err?: any): void }
  export interface Router { [key: string]: any }
  const e: any;
  export const Router: any;
  export default e;
}
declare module 'cors' { const value: any; export default value; }
declare module 'helmet' { const value: any; export default value; }
declare module 'express-rate-limit' { const value: any; export default value; }
declare module 'dotenv' { const value: any; export default value; }
declare module 'joi' { const value: any; export default value; export type ObjectSchema = any; export const object: any; }
declare module 'pg' { export const Pool: any; export type PoolClient = any; export type QueryResult<T = unknown> = any; }
declare module 'jsonwebtoken' { const value: any; export default value; }
declare module 'bcryptjs' { const value: any; export default value; }
declare module 'uuid' { export const v4: any; }
declare const process: any;
