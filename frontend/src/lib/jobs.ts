import { apiJson } from "./api";

export type JobCardItem = {
	id: string;
	title: string;
	salary: string;
	company: string;
	location: string;
	risk_flags: string[];
	score_avg: number;
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
};

type JobsResponse = {
	ok: boolean;
	data?: {
		total: number;
		jobs: JobCardItem[];
	};
};

export async function fetchJobs(q = "", limit = 60): Promise<JobCardItem[]> {
	const query = new URLSearchParams();
	query.set("limit", String(limit));
	if (q.trim()) query.set("q", q.trim());

	const res = await apiJson<JobsResponse>(`/api/jobs?${query.toString()}`);
	if (!res.ok || !res.data?.jobs) return [];
	return res.data.jobs;
}
