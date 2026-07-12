import { getBearerToken } from "./bearer";
import { apiFetch } from "./http";

export interface PersonalityQuestion {
	id: number;
	question_text: string;
	option_a: string;
	option_b: string;
	dimension: string;
	option_a_type: string;
	option_b_type: string;
}

export interface PersonalityAnswer {
	question_id: number;
	user_choice: string;
}

export interface DimensionAnalysis {
	dimension: string;
	type: string;
	name: string;
	description: string;
	characteristics: string[];
	work_preference: string[];
	growth_suggestions: string[];
}

export interface CompleteAnalysis {
	type: string;
	name: string;
	summary: string;
	core_strengths: string[];
	career_tendencies: string[];
	workplace_relationships: string[];
	development_areas: string[];
	stress_response: string;
}

export interface JobRecommendation {
	recommended_jobs: string[];
	career_advice: string;
}

export interface PersonalityResult {
	mbti_type: string;
	personality_analysis: string;
	recommended_jobs: string[];
	dimension_analysis: DimensionAnalysis[];
	complete_analysis: CompleteAnalysis;
	job_recommendations: JobRecommendation;
	profile_id: number;
}

type PersonalityApiResponse<T> = {
	code: number;
	msg?: string;
	data: T;
};

export async function fetchPersonalityQuestions(): Promise<PersonalityQuestion[]> {
	const res = await apiFetch("/api/personality/questions");
	const json = (await res.json()) as PersonalityApiResponse<PersonalityQuestion[]>;
	if (!res.ok || json.code !== 200 || !Array.isArray(json.data)) {
		throw new Error(json.msg || "加载题目失败");
	}
	return json.data;
}

export async function submitPersonalityAnswers(
	answers: PersonalityAnswer[],
): Promise<PersonalityResult> {
	const token = getBearerToken();
	if (!token) {
		throw new Error("请先登录后再提交性格测试");
	}

	const res = await apiFetch("/api/personality/submit", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({ answers }),
	});

	const json = (await res.json()) as PersonalityApiResponse<PersonalityResult>;
	if (!res.ok || json.code !== 200 || !json.data) {
		throw new Error(json.msg || "提交答案失败");
	}
	return json.data;
}
