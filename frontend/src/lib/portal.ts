import type { Action } from "svelte/action";

/**
 * 将节点移到 document.body，避免祖先带 transform（如 .onload-animation）导致 position:fixed 错位。
 */
export const portal: Action<HTMLElement, HTMLElement | undefined> = (node, target) => {
	if (typeof document === "undefined") {
		return {};
	}
	const t = target ?? document.body;
	t.appendChild(node);
	return {
		destroy() {
			node.remove();
		},
	};
};
