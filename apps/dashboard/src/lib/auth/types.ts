export type SignInMethod = "email" | "google";

export type AuthUser = {
  id: string;
  email: string;
  name?: string | null;
  emailVerified?: boolean;
};

export type Session = { token: string; user: AuthUser };
