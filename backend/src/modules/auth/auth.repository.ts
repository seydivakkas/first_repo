import { v4 as uuid } from 'uuid';

export type User = { id: string; email: string; passwordHash: string; role: 'user' | 'admin'; name: string };
const users: User[] = [];

export const authRepository = {
  create(email: string, passwordHash: string, name: string): User {
    const user: User = { id: uuid(), email, passwordHash, role: 'user', name };
    users.push(user);
    return user;
  },
  findByEmail(email: string): User | undefined {
    return users.find((u) => u.email === email);
  },
  findById(id: string): User | undefined {
    return users.find((u) => u.id === id);
  },
  update(id: string, patch: Partial<Pick<User, 'name' | 'passwordHash'>>): User | undefined {
    const user = users.find((u) => u.id === id);
    if (!user) return undefined;
    Object.assign(user, patch);
    return user;
  }
};
