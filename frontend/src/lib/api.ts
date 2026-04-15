/**
 * Flask 后端 API 封装。开发环境通过 Vite 代理访问 `/api`；
 * 生产环境可设 `PUBLIC_API_BASE` 为空（同源）或完整 API 根路径。
 */
function apiBase(): string {
	const raw = import.meta.env.PUBLIC_API_BASE;
	if (raw === undefined || raw === "") {
		return "";
	}
	return raw.replace(/\/$/, "");
}

export async function apiFetch(
	path: string,
	init?: RequestInit,
): Promise<Response> {
	const url = `${apiBase()}${path.startsWith("/") ? path : `/${path}`}`;
	return fetch(url, {
		...init,
		headers: {
			Accept: "application/json",
			...init?.headers,
		},
	});
}

export async function apiJson<T>(
	path: string,
	init?: RequestInit,
): Promise<T> {
	const res = await apiFetch(path, init);
	if (!res.ok) {
		const text = await res.text().catch(() => "");
		throw new Error(
			`API ${path} failed: ${res.status} ${res.statusText} ${text}`,
		);
	}
	return res.json() as Promise<T>;
}
