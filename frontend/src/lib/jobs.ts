import { apiJson } from "./api";
import { getToken } from "./auth";

export type JobCardItem = {
	id: string;
	title: string;
	salary: string;
	company: string;
	location: string;
	risk_flags: string[];
	score_avg: number;
	conf_avg: number;
	scores: {
		cap_req_theory: number;
		cap_req_cross: number;
		cap_req_practice: number;
		cap_req_digital: number;
		cap_req_innovation: number;
		cap_req_teamwork: number;
		cap_req_social: number;
		cap_req_growth: number;
	};
	confidences: {
		cap_conf_theory: number;
		cap_conf_cross: number;
		cap_conf_practice: number;
		cap_conf_digital: number;
		cap_conf_innovation: number;
		cap_conf_teamwork: number;
		cap_conf_social: number;
		cap_conf_growth: number;
	};
};

export type JobRequirement = {
	name: string;
	label: string;
	level: string;
};

export type JobDetailItem = JobCardItem & {
	industry: string;
	company_type: string;
	company_size: string;
	company_detail: string;
	demand: string;
	experience_text: string;
	experience_years: number;
	internship_req: string;
	updated_date: string;
	source_url: string;
	cap_evidence: string[];
	requirements: JobRequirement[];
};

type JobsResponse = {
	ok: boolean;
	data?: {
		total: number;
		page: number;
		page_size: number;
		total_pages: number;
		jobs: JobCardItem[];
	};
};

type JobDetailResponse = {
	ok: boolean;
	data?: JobDetailItem;
};

export type AssistantSessionItem = {
	id: number;
	title: string;
	created_at: string;
	updated_at: string;
	last_message_at: string;
};

export type AssistantMessageItem = {
	id: number;
	role: "user" | "assistant";
	content: string;
	filters_json: Record<string, unknown>;
	result_job_ids_json: string[];
	is_saved: boolean;
	created_at?: string;
};

export type AssistantChatResult = {
	session_id: number;
	filters: Record<string, unknown>;
	jobs: JobCardItem[];
	user_message: {
		id: number;
		role: "user";
		content: string;
		is_saved: boolean;
	};
	assistant_message: {
		id: number;
		role: "assistant";
		content: string;
		is_saved: boolean;
	};
};

type AssistantSessionsResponse = {
	ok: boolean;
	data?: {
		sessions: AssistantSessionItem[];
	};
};

type AssistantSessionDetailResponse = {
	ok: boolean;
	data?: {
		session: AssistantSessionItem;
		messages: AssistantMessageItem[];
		jobs: JobCardItem[];
		filters: Record<string, unknown>;
	};
};

type AssistantChatResponse = {
	ok: boolean;
	data?: AssistantChatResult;
};

type AssistantSaveResponse = {
	ok: boolean;
	message?: string;
};

export type FetchJobsParams = {
	q?: string;
	page?: number;
	pageSize?: number;
};

export type JobsPageResult = {
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
	jobs: JobCardItem[];
};

export async function fetchJobs(params: FetchJobsParams = {}): Promise<JobsPageResult> {
	const { q = "", page = 1, pageSize = 40 } = params;
	const query = new URLSearchParams();
	query.set("page", String(page));
	query.set("page_size", String(pageSize));
	if (q.trim()) query.set("q", q.trim());

	const res = await apiJson<JobsResponse>(`/api/jobs?${query.toString()}`);
	if (!res.ok || !res.data?.jobs) {
		return { total: 0, page: 1, pageSize, totalPages: 1, jobs: [] };
	}
	return {
		total: res.data.total,
		page: res.data.page,
		pageSize: res.data.page_size,
		totalPages: res.data.total_pages,
		jobs: res.data.jobs,
	};
}

export async function fetchJobDetail(jobId: string): Promise<JobDetailItem> {
	const id = jobId.trim();
	if (!id) {
		throw new Error("岗位 ID 不能为空");
	}
	const res = await apiJson<JobDetailResponse>(`/api/jobs/${encodeURIComponent(id)}`);
	if (!res.ok || !res.data) {
		throw new Error("获取岗位详情失败");
	}
	return res.data;
}

function authHeaders(): HeadersInit {
	const token = getToken();
	if (!token) {
		throw new Error("请先登录后再使用 AI 助手");
	}
	return {
		Authorization: `Bearer ${token}`,
		"Content-Type": "application/json",
	};
}

export async function chatJobsAssistant(input: {
	message: string;
	sessionId?: number;
}): Promise<AssistantChatResult> {
	const message = input.message.trim();
	if (!message) {
		throw new Error("请输入问题后再发送");
	}
	const res = await apiJson<AssistantChatResponse>("/api/jobs/assistant/chat", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({
			message,
			session_id: input.sessionId,
		}),
	});
	if (!res.ok || !res.data) {
		throw new Error("AI 助手请求失败");
	}
	return res.data;
}

export async function listAssistantSessions(): Promise<AssistantSessionItem[]> {
	const res = await apiJson<AssistantSessionsResponse>("/api/jobs/assistant/sessions", {
		method: "GET",
		headers: authHeaders(),
	});
	if (!res.ok || !res.data?.sessions) {
		return [];
	}
	return res.data.sessions;
}

export async function getAssistantSessionDetail(
	sessionId: number,
): Promise<AssistantSessionDetailResponse["data"]> {
	const res = await apiJson<AssistantSessionDetailResponse>(`/api/jobs/assistant/sessions/${sessionId}`, {
		method: "GET",
		headers: authHeaders(),
	});
	if (!res.ok || !res.data) {
		throw new Error("加载会话失败");
	}
	return res.data;
}

export async function saveAssistantMessage(messageId: number): Promise<string> {
	const res = await apiJson<AssistantSaveResponse>(`/api/jobs/assistant/messages/${messageId}/save`, {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({}),
	});
	if (!res.ok) {
		throw new Error("保存失败");
	}
	return res.message || "已保存";
}
