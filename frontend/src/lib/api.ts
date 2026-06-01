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

/** 从失败响应体中提取后端返回的可读错误文案（支持 `message` / `msg`）。 */
function extractApiErrorMessage(
	text: string,
	status: number,
	statusText: string,
): string {
	const trimmed = text.trim();
	if (!trimmed) {
		return `请求失败（${status} ${statusText}）`;
	}
	try {
		const body = JSON.parse(trimmed) as Record<string, unknown>;
		const msg = body.message ?? body.msg;
		if (typeof msg === "string" && msg.trim()) {
			return msg.trim();
		}
	} catch {
		// 非 JSON 响应（如 Nginx 502 页面）走下方兜底
	}
	return `请求失败（${status}）`;
}

export async function apiJson<T>(
	path: string,
	init?: RequestInit,
): Promise<T> {
	const res = await apiFetch(path, init);
	if (!res.ok) {
		const text = await res.text().catch(() => "");
		throw new Error(extractApiErrorMessage(text, res.status, res.statusText));
	}
	return res.json() as Promise<T>;
}
