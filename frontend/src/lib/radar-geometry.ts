/**
 * 岗位探索与人岗/能力画像共用的八维雷达几何（与 JobsExplorer 卡片一致）
 */
import type { JobCardItem } from "@/lib/jobs";

export const RADAR_DIMENSIONS: {
	key: keyof JobCardItem["scores"];
	label: string;
	full: string;
}[] = [
	{ key: "cap_req_theory", label: "理论知识", full: "专业理论知识" },
	{ key: "cap_req_cross", label: "交叉广度", full: "交叉学科广度" },
	{ key: "cap_req_practice", label: "实践技能", full: "专业实践技能" },
	{ key: "cap_req_digital", label: "数字素养", full: "数字素养技能" },
	{ key: "cap_req_innovation", label: "创新创业", full: "创新创业能力" },
	{ key: "cap_req_teamwork", label: "团队协作", full: "团队协作能力" },
	{ key: "cap_req_social", label: "社会实践", full: "社会实践网络" },
	{ key: "cap_req_growth", label: "学习发展", full: "学习与发展潜力" },
];

export const RADAR_TIERS = [0.25, 0.5, 0.75, 1] as const;
export const RADAR_CX = 140;
export const RADAR_CY = 120;
export const RADAR_MAX_R = 88;
export const RADAR_LABEL_R = 110;

const N = RADAR_DIMENSIONS.length;

export function radarPoint(angleIndex: number, value: number) {
	const angle = (-Math.PI / 2 + (angleIndex * 2 * Math.PI) / N) % (2 * Math.PI);
	const r = (Math.max(0, Math.min(100, value)) / 100) * RADAR_MAX_R;
	return { x: RADAR_CX + r * Math.cos(angle), y: RADAR_CY + r * Math.sin(angle) };
}

export function radarPointByRadius(angleIndex: number, radius: number) {
	const angle = (-Math.PI / 2 + (angleIndex * 2 * Math.PI) / N) % (2 * Math.PI);
	return {
		x: RADAR_CX + radius * Math.cos(angle),
		y: RADAR_CY + radius * Math.sin(angle),
	};
}

export function calcRadarPolygonPoints(job: Pick<JobCardItem, "scores">): string {
	const points = RADAR_DIMENSIONS.map((d, idx) => {
		const p = radarPoint(idx, job.scores[d.key]);
		return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
	});
	return points.join(" ");
}

export function calcRadarGridPolygon(tier: number): string {
	const points = RADAR_DIMENSIONS.map((_, idx) => {
		const p = radarPoint(idx, 100 * tier);
		return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
	});
	return points.join(" ");
}

export function radarAxisEnd(idx: number) {
	const p = radarPoint(idx, 100);
	return { x: p.x, y: p.y };
}

export function radarLabelPos(idx: number) {
	const p = radarPointByRadius(idx, RADAR_LABEL_R);
	return { x: p.x, y: p.y };
}

export function emptyCapabilityScores(): JobCardItem["scores"] {
	return {
		cap_req_theory: 0,
		cap_req_cross: 0,
		cap_req_practice: 0,
		cap_req_digital: 0,
		cap_req_innovation: 0,
		cap_req_teamwork: 0,
		cap_req_social: 0,
		cap_req_growth: 0,
	};
}

/** 简历解析回调里 theory/cross/... 与 cap_req_* 对齐 */
export function mapProfileDetailToScores(detail: Record<string, unknown>): JobCardItem["scores"] {
	const n = (v: unknown) => {
		const x = Number(v);
		return Number.isFinite(x) ? x : 0;
	};
	return {
		cap_req_theory: n(detail.theory),
		cap_req_cross: n(detail.cross),
		cap_req_practice: n(detail.practice),
		cap_req_digital: n(detail.digital),
		cap_req_innovation: n(detail.innovation),
		cap_req_teamwork: n(detail.teamwork),
		cap_req_social: n(detail.social),
		cap_req_growth: n(detail.growth),
	};
}
