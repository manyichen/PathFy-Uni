<script lang="ts">
let over = $state(false);
let fileName = $state<string | null>(null);
let inputId = "resume-file-input";

function onDragOver(e: DragEvent) {
	e.preventDefault();
	over = true;
}

function onDragLeave() {
	over = false;
}

function onDrop(e: DragEvent) {
	e.preventDefault();
	over = false;
	const f = e.dataTransfer?.files?.[0];
	fileName = f?.name ?? null;
}

function onFile(e: Event) {
	const input = e.target as HTMLInputElement;
	const f = input.files?.[0];
	fileName = f?.name ?? null;
}
</script>

<div
	class="relative overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-300 {over
		? 'border-[var(--primary)] bg-[color-mix(in_oklch,var(--primary)_12%,transparent)] scale-[1.01]'
		: 'border-black/20 bg-[var(--btn-regular-bg)] dark:border-white/20'}"
	ondragover={onDragOver}
	ondragleave={onDragLeave}
	ondrop={onDrop}
>
	<div class="flex flex-col items-center justify-center gap-4 px-6 py-14 text-center">
		<div
			class="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--card-bg)] text-3xl shadow-md transition-transform duration-300 {over
				? 'scale-110 rotate-6'
				: ''}"
			aria-hidden="true"
		>
			📄
		</div>
		<div>
			<p class="font-semibold text-black dark:text-white">
				{over ? "松开以上传" : "拖拽简历到此处"}
			</p>
			<p class="mt-1 text-sm text-75">支持 PDF / Word / TXT（演示，未调用后端）</p>
		</div>
		<label
			for={inputId}
			class="btn-regular z-10 cursor-pointer rounded-xl px-6 py-2.5 text-sm font-semibold"
		>
			选择本地文件
		</label>
		<input
			id={inputId}
			type="file"
			accept=".pdf,.doc,.docx,.txt"
			class="sr-only"
			onchange={onFile}
		/>
		{#if fileName}
			<p
				class="rounded-full bg-[var(--primary)]/15 px-4 py-1.5 text-sm font-medium text-[var(--primary)]"
			>
				已选择：{fileName}
			</p>
		{/if}
	</div>
</div>
