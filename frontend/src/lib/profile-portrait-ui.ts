/**
 * 能力画像页：完整度/竞争力文案与 DOM 更新（供上传成功与刷新后从服务端恢复共用）
 */
import type { JobCardItem } from "@/lib/jobs";

export type PortraitScoresShape = JobCardItem["scores"];

function getWeakDimensions(scores: PortraitScoresShape): string {
	const dimensions = [
		{ name: "专业理论知识", value: scores.cap_req_theory },
		{ name: "交叉学科广度", value: scores.cap_req_cross },
		{ name: "专业实践技能", value: scores.cap_req_practice },
		{ name: "数字素养技能", value: scores.cap_req_digital },
		{ name: "创新创业能力", value: scores.cap_req_innovation },
		{ name: "团队协作能力", value: scores.cap_req_teamwork },
		{ name: "社会实践网络", value: scores.cap_req_social },
		{ name: "学习与发展潜力", value: scores.cap_req_growth },
	];
	return dimensions
		.sort((a, b) => a.value - b.value)
		.slice(0, 2)
		.map((d) => d.name)
		.join("、");
}

function getStrongDimensions(scores: PortraitScoresShape): string {
	const dimensions = [
		{ name: "专业理论知识", value: scores.cap_req_theory },
		{ name: "交叉学科广度", value: scores.cap_req_cross },
		{ name: "专业实践技能", value: scores.cap_req_practice },
		{ name: "数字素养技能", value: scores.cap_req_digital },
		{ name: "创新创业能力", value: scores.cap_req_innovation },
		{ name: "团队协作能力", value: scores.cap_req_teamwork },
		{ name: "社会实践网络", value: scores.cap_req_social },
		{ name: "学习与发展潜力", value: scores.cap_req_growth },
	];
	return dimensions
		.sort((a, b) => b.value - a.value)
		.slice(0, 2)
		.map((d) => d.name)
		.join("、");
}

export function generateCompletenessAnalysis(
	completeness: number,
	scores: PortraitScoresShape,
): string {
	if (completeness >= 90) {
		return "您的能力覆盖非常全面，各维度发展均衡，展现了良好的综合能力素质。建议继续保持各维度的发展，同时可以尝试在特定领域进行深度拓展。";
	}
	if (completeness >= 70) {
		return `您的能力覆盖较为全面，大部分维度发展良好。建议关注发展相对薄弱的维度，如${getWeakDimensions(scores)}，以提升整体能力的完整性。`;
	}
	if (completeness >= 50) {
		return `您的能力覆盖存在一定的不平衡，部分维度发展较好，但其他维度相对薄弱。建议重点加强${getWeakDimensions(scores)}等维度的培养，以提高能力的整体完整性。`;
	}
	return `您的能力覆盖较为有限，多个维度发展不足。建议系统性地提升各维度能力，特别是${getWeakDimensions(scores)}等核心维度，以建立更加完整的能力体系。`;
}

export function generateCompetitivenessAnalysis(
	competitiveness: number,
	scores: PortraitScoresShape,
): string {
	if (competitiveness >= 90) {
		return "您的就业竞争力非常强，在各维度都展现出了突出的能力。建议保持优势，同时关注行业最新发展趋势，持续提升专业技能，以保持竞争力。";
	}
	if (competitiveness >= 70) {
		return `您的就业竞争力较强，在多个维度表现良好。建议强化${getStrongDimensions(scores)}等优势维度，同时提升${getWeakDimensions(scores)}等薄弱环节，以进一步增强竞争力。`;
	}
	if (competitiveness >= 50) {
		return `您的就业竞争力处于中等水平，有一定的优势但也存在明显的不足。建议重点提升${getWeakDimensions(scores)}等维度，同时加强实践经验和项目经历的积累。`;
	}
	return `您的就业竞争力相对较弱，需要全面提升各维度能力。建议从${getWeakDimensions(scores)}等基础维度入手，逐步建立核心竞争力，同时积累相关实践经验。`;
}

function setText(id: string, text: string | number): void {
	const el = document.getElementById(id);
	if (el) el.textContent = String(text);
}

function setInputValue(id: string, value: string): void {
	const el = document.getElementById(id) as HTMLInputElement | null;
	if (el) el.value = value;
}

function dispatchRadar(scores: PortraitScoresShape): void {
	const radarDetail = {
		theory: scores.cap_req_theory,
		cross: scores.cap_req_cross,
		practice: scores.cap_req_practice,
		digital: scores.cap_req_digital,
		innovation: scores.cap_req_innovation,
		teamwork: scores.cap_req_teamwork,
		social: scores.cap_req_social,
		growth: scores.cap_req_growth,
	};
	window.dispatchEvent(new CustomEvent("updateRadarScores", { detail: radarDetail }));
}

/** 供页面在 Svelte 雷达挂载后再触发一次，避免刷新后竞态漏绘 */
export function emitProfileRadarScores(scores: PortraitScoresShape): void {
	dispatchRadar(scores);
	requestAnimationFrame(() => dispatchRadar(scores));
}

export function paintProfilePortraitPage(opts: {
	scores: PortraitScoresShape;
	completeness: number;
	competitiveness: number;
	name?: string;
	major?: string;
}): void {
	const { scores, completeness, competitiveness, name, major } = opts;

	setText("score_theory", scores.cap_req_theory);
	setText("score_cross", scores.cap_req_cross);
	setText("score_practice", scores.cap_req_practice);
	setText("score_digital", scores.cap_req_digital);
	setText("score_innovation", scores.cap_req_innovation);
	setText("score_teamwork", scores.cap_req_teamwork);
	setText("score_social", scores.cap_req_social);
	setText("score_growth", scores.cap_req_growth);

	setText("completeness_score", completeness);
	setText("competitiveness_score", competitiveness);
	const cBar = document.getElementById("completeness_bar") as HTMLElement | null;
	const pBar = document.getElementById("competitiveness_bar") as HTMLElement | null;
	if (cBar) cBar.style.width = `${completeness}%`;
	if (pBar) pBar.style.width = `${competitiveness}%`;

	const ca = document.getElementById("completeness_analysis");
	const pa = document.getElementById("competitiveness_analysis");
	if (ca) ca.textContent = generateCompletenessAnalysis(completeness, scores);
	if (pa) pa.textContent = generateCompetitivenessAnalysis(competitiveness, scores);

	if (name !== undefined) setInputValue("nameInput", name);
	if (major !== undefined) setInputValue("majorInput", major);

	emitProfileRadarScores(scores);
}

export const PROFILE_PORTRAIT_LOCAL_KEY = (userId: number) => `career_profile_portrait_v1_${userId}`;

export type PortraitLocalCache = {
	v: 1;
	scores: PortraitScoresShape;
	completeness: number;
	competitiveness: number;
	name: string;
	major: string;
	savedAt: string;
};

export function savePortraitLocalCache(userId: number, data: Omit<PortraitLocalCache, "v" | "savedAt">): void {
	try {
		const payload: PortraitLocalCache = {
			v: 1,
			...data,
			savedAt: new Date().toISOString(),
		};
		localStorage.setItem(PROFILE_PORTRAIT_LOCAL_KEY(userId), JSON.stringify(payload));
	} catch {
		/* ignore quota */
	}
}

export function loadPortraitLocalCache(userId: number): PortraitLocalCache | null {
	try {
		const raw = localStorage.getItem(PROFILE_PORTRAIT_LOCAL_KEY(userId));
		if (!raw) return null;
		const o = JSON.parse(raw) as PortraitLocalCache;
		if (o?.v !== 1 || !o.scores || typeof o.scores.cap_req_theory !== "number") return null;
		return o;
	} catch {
		return null;
	}
}
