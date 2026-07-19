import { Pool, PoolClient, QueryResult } from 'pg';
import { env } from './env';

const pool = new Pool({ connectionString: env.databaseUrl });

export const query = <T = unknown>(text: string, params?: unknown[]): Promise<QueryResult<T>> => {
  return pool.query(text, params);
};

export const getClient = (): Promise<PoolClient> => pool.connect();
