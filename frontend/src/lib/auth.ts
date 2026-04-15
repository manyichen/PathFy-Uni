import { apiJson } from "./api";

export type AuthUser = {
	id: number;
	username: string;
	email: string;
};

type AuthResponse = {
	ok: boolean;
	message: string;
	data?: {
		token: string;
		user: AuthUser;
	};
};

type MeResponse = {
	ok: boolean;
	data?: {
		user: AuthUser;
	};
};

const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

function isBrowser(): boolean {
	return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

export function saveAuth(token: string, user: AuthUser): void {
	if (!isBrowser()) return;
	localStorage.setItem(TOKEN_KEY, token);
	localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
	if (!isBrowser()) return;
	localStorage.removeItem(TOKEN_KEY);
	localStorage.removeItem(USER_KEY);
}

export function getToken(): string | null {
	if (!isBrowser()) return null;
	return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
	if (!isBrowser()) return null;
	const raw = localStorage.getItem(USER_KEY);
	if (!raw) return null;
	try {
		return JSON.parse(raw) as AuthUser;
	} catch {
		return null;
	}
}

export async function register(
	username: string,
	email: string,
	password: string,
): Promise<AuthResponse> {
	return apiJson<AuthResponse>("/api/auth/register", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ username, email, password }),
	});
}

export async function login(
	account: string,
	password: string,
): Promise<AuthResponse> {
	return apiJson<AuthResponse>("/api/auth/login", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ account, password }),
	});
}

export async function fetchMe(token: string): Promise<AuthUser> {
	const res = await apiJson<MeResponse>("/api/auth/me", {
		method: "GET",
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});
	if (!res.ok || !res.data?.user) {
		throw new Error("获取用户信息失败");
	}
	return res.data.user;
}
