import dotenv from 'dotenv';
import Joi from 'joi';

dotenv.config();

const schema = Joi.object({
  PORT: Joi.number().default(4000),
  NODE_ENV: Joi.string().valid('development', 'test', 'production').default('development'),
  DATABASE_URL: Joi.string().required(),
  JWT_SECRET: Joi.string().required(),
  JWT_EXPIRES_IN: Joi.string().default('1d'),
  FRONTEND_ORIGIN: Joi.string().default('http://localhost:5173')
}).unknown();

const { error, value } = schema.validate(process.env, { abortEarly: false });
if (error) {
  throw new Error(`Environment validation failed: ${error.message}`);
}

export const env = {
  port: Number(value.PORT),
  nodeEnv: value.NODE_ENV as string,
  databaseUrl: value.DATABASE_URL as string,
  jwtSecret: value.JWT_SECRET as string,
  jwtExpiresIn: value.JWT_EXPIRES_IN as string,
  frontendOrigin: value.FRONTEND_ORIGIN as string
};
