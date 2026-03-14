import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { env } from '../../config/env';
import { authRepository } from './auth.repository';

export const authService = {
  async register(email: string, password: string, name: string) {
    if (authRepository.findByEmail(email)) throw new Error('Email already registered');
    const passwordHash = await bcrypt.hash(password, 10);
    const user = authRepository.create(email, passwordHash, name);
    return this.sign(user.id, user.email, user.role);
  },
  async login(email: string, password: string) {
    const user = authRepository.findByEmail(email);
    if (!user || !(await bcrypt.compare(password, user.passwordHash))) throw new Error('Invalid credentials');
    return this.sign(user.id, user.email, user.role);
  },
  getProfile(id: string) {
    const user = authRepository.findById(id);
    if (!user) throw new Error('User not found');
    return { id: user.id, email: user.email, name: user.name, role: user.role };
  },
  async updateProfile(id: string, name: string) {
    const user = authRepository.update(id, { name });
    if (!user) throw new Error('User not found');
    return this.getProfile(id);
  },
  async changePassword(id: string, currentPassword: string, newPassword: string) {
    const user = authRepository.findById(id);
    if (!user || !(await bcrypt.compare(currentPassword, user.passwordHash))) throw new Error('Invalid current password');
    const passwordHash = await bcrypt.hash(newPassword, 10);
    authRepository.update(id, { passwordHash });
    return { message: 'Password updated' };
  },
  sign(id: string, email: string, role: string) {
    const token = jwt.sign({ id, email, role }, env.jwtSecret, { expiresIn: env.jwtExpiresIn });
    return { token };
  }
};
