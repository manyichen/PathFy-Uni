import { getUser, PERSONALITY_CACHE_KEY_PREFIX } from "./auth";

export function getPersonalityTestStorageKey(): string {
	const u = getUser();
	const id = u?.id != null ? String(u.id) : "guest";
	return `${PERSONALITY_CACHE_KEY_PREFIX}${id}`;
}

export type PersonalityTestPersisted = {
	v: 1;
	questionCount: number;
	showStartScreen: boolean;
	showResults: boolean;
	currentQuestionIndex: number;
	answers: { question_id: number; user_choice: string }[];
	personalityProfile: unknown | null;
	savedAt: string;
};

export function loadPersonalityTestCache(
	questionCount: number,
): PersonalityTestPersisted | null {
	if (typeof window === "undefined") return null;
	try {
		const raw = localStorage.getItem(getPersonalityTestStorageKey());
		if (!raw) return null;
		const o = JSON.parse(raw) as PersonalityTestPersisted;
		if (o?.v !== 1 || o.questionCount !== questionCount) return null;
		if (!Array.isArray(o.answers)) return null;
		return o;
	} catch {
		return null;
	}
}

export function savePersonalityTestCache(
	payload: Omit<PersonalityTestPersisted, "v" | "savedAt">,
): void {
	if (typeof window === "undefined") return;
	try {
		const full: PersonalityTestPersisted = {
			v: 1,
			...payload,
			savedAt: new Date().toISOString(),
		};
		localStorage.setItem(
			getPersonalityTestStorageKey(),
			JSON.stringify(full),
		);
	} catch {
		/* quota */
	}
}

export function clearPersonalityTestCache(): void {
	if (typeof window === "undefined") return;
	try {
		localStorage.removeItem(getPersonalityTestStorageKey());
	} catch {
		/* ignore */
	}
}
