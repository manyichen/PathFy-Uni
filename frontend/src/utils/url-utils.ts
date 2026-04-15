/** 兼容 suillilab 的 base 路径拼接（当前 base 为 `/`） */
export function url(path: string): string {
	if (path.startsWith("http://") || path.startsWith("https://")) {
		return path;
	}
	const base = import.meta.env.BASE_URL.replace(/\/$/, "") || "";
	const p = path.startsWith("/") ? path : `/${path}`;
	return `${base}${p}`;
}
