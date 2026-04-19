

export interface PortraitScores {
  cap_req_theory: number;
  cap_req_cross: number;
  cap_req_practice: number;
  cap_req_digital: number;
  cap_req_innovation: number;
  cap_req_teamwork: number;
  cap_req_social: number;
  cap_req_growth: number;
}

export interface PortraitResult {
  resume_id: number;
  scores: PortraitScores;
  completeness: number;
  competitiveness: number;
  detailed_analysis?: any;
}

export async function uploadResume(data: FormData) {
  const res = await fetch("http://localhost:5000/api/profile/upload", {
    method: 'POST',
    body: data
  });

  const json = await res.json();
  if (json.code !== 200) throw new Error(json.msg || '分析失败');
  return json.data as PortraitResult;
}