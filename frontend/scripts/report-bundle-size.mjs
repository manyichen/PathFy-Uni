import { readFile, readdir, stat, writeFile } from 'node:fs/promises'
import { extname, join, relative, resolve } from 'node:path'
import { gzipSync } from 'node:zlib'

const root = resolve(import.meta.dirname, '..')
const publicDir = join(root, '.output', 'public')
const budgetPath = join(root, 'bundle-budget.json')
const reportPath = join(root, '.output', 'bundle-report.json')
const shouldCheck = process.argv.includes('--check')

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? walk(path) : [path]
  }))
  return nested.flat()
}

function sum(items, key) {
  return items.reduce((total, item) => total + item[key], 0)
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`
  return `${(value / 1024).toFixed(1)} KiB`
}

async function main() {
  try {
    await stat(publicDir)
  } catch {
    throw new Error('Missing .output/public. Run `pnpm generate` before the bundle report.')
  }

  const files = await walk(publicDir)
  const assets = await Promise.all(files.map(async (path) => {
    const content = await readFile(path)
    return {
      file: relative(publicDir, path).replaceAll('\\', '/'),
      extension: extname(path).toLowerCase(),
      bytes: content.byteLength,
      gzipBytes: gzipSync(content).byteLength
    }
  }))

  const js = assets.filter(item => item.extension === '.js')
  const css = assets.filter(item => item.extension === '.css')
  const html = assets.filter(item => item.extension === '.html')
  const largestJs = [...js].sort((a, b) => b.bytes - a.bytes).slice(0, 10)
  const indexHtml = await readFile(join(publicDir, 'index.html'), 'utf8')
  const homepageRefs = [...indexHtml.matchAll(/(?:src|href)=["']\/?(_nuxt\/[^"']+\.(?:js|css))["']/g)]
    .map(match => match[1])
    .filter((file, index, all) => all.indexOf(file) === index)
  const homepageAssets = homepageRefs.map(file => assets.find(item => item.file === file)).filter(Boolean)
  const echartsChunks = []
  const authJourneyChunks = []
  const careerGraphChunks = []
  const profileEvidenceChunks = []
  const matchTensionChunks = []
  const personalityFingerprintChunks = []
  const reportPathChunks = []
  const jobConstellationChunks = []
  const homeWorkflowExperienceChunks = []
  for (const item of js) {
    const content = await readFile(join(publicDir, item.file), 'utf8')
    if (/zrender|echarts/i.test(content)) echartsChunks.push(item)
    if (/_addAccsOutput|p5\.js says:/i.test(content)) authJourneyChunks.push(item)
    if (/PATH RELATIONSHIP MAP|career-graph-canvas/.test(content)) careerGraphChunks.push(item)
    if (/profile-evidence-canvas|画像形成过程/.test(content)) profileEvidenceChunks.push(item)
    if (/match-tension-canvas|能力张力场/.test(content)) matchTensionChunks.push(item)
    if (/personality-fingerprint-canvas|人格视觉指纹/.test(content)) personalityFingerprintChunks.push(item)
    if (/report-path-canvas|报告真实状态路径/.test(content)) reportPathChunks.push(item)
    if (/job-constellation-canvas|岗位星群/.test(content)) jobConstellationChunks.push(item)
    if (/home-workflow-experience-canvas|职业规划五阶段路径体验/.test(content)) homeWorkflowExperienceChunks.push(item)
  }
  const careerGraphCss = []
  const profileEvidenceCss = []
  const matchTensionCss = []
  const personalityFingerprintCss = []
  const reportPathCss = []
  const jobConstellationCss = []
  const homeWorkflowExperienceCss = []
  for (const item of css) {
    const content = await readFile(join(publicDir, item.file), 'utf8')
    if (/career-graph-explorer/.test(content)) careerGraphCss.push(item)
    if (/profile-evidence-heading/.test(content)) profileEvidenceCss.push(item)
    if (/match-tension-heading/.test(content)) matchTensionCss.push(item)
    if (/personality-fingerprint-heading/.test(content)) personalityFingerprintCss.push(item)
    if (/report-path-heading/.test(content)) reportPathCss.push(item)
    if (/job-constellation-heading/.test(content)) jobConstellationCss.push(item)
    if (/home-workflow-experience/.test(content)) homeWorkflowExperienceCss.push(item)
  }
  const homepageEcharts = echartsChunks.filter(item => homepageRefs.includes(item.file))
  const homepageAuthJourney = authJourneyChunks.filter(item => homepageRefs.includes(item.file))
  const homepageCareerGraph = careerGraphChunks.filter(item => homepageRefs.includes(item.file))
  const homepageProfileEvidence = profileEvidenceChunks.filter(item => homepageRefs.includes(item.file))
  const homepageMatchTension = matchTensionChunks.filter(item => homepageRefs.includes(item.file))
  const homepagePersonalityFingerprint = personalityFingerprintChunks.filter(item => homepageRefs.includes(item.file))
  const homepageReportPath = reportPathChunks.filter(item => homepageRefs.includes(item.file))
  const homepageJobConstellation = jobConstellationChunks.filter(item => homepageRefs.includes(item.file))
  const homepageWorkflowExperience = homeWorkflowExperienceChunks.filter(item => homepageRefs.includes(item.file))
  const budget = JSON.parse(await readFile(budgetPath, 'utf8'))
  const totals = {
    publicBytes: sum(assets, 'bytes'),
    publicGzipBytes: sum(assets, 'gzipBytes'),
    jsBytes: sum(js, 'bytes'),
    jsGzipBytes: sum(js, 'gzipBytes'),
    cssBytes: sum(css, 'bytes'),
    cssGzipBytes: sum(css, 'gzipBytes'),
    htmlBytes: sum(html, 'bytes'),
    htmlGzipBytes: sum(html, 'gzipBytes'),
    largestJsChunkBytes: largestJs[0]?.bytes ?? 0
  }
  const homepageInitial = {
    files: homepageRefs,
    bytes: sum(homepageAssets, 'bytes'),
    gzipBytes: sum(homepageAssets, 'gzipBytes'),
    loadsEcharts: homepageEcharts.length > 0,
    loadsAuthJourney: homepageAuthJourney.length > 0
  }
  const authJourneyBytes = sum(authJourneyChunks, 'bytes')
  const authJourneyGzipBytes = sum(authJourneyChunks, 'gzipBytes')
  const baseJsBytes = totals.jsBytes - authJourneyBytes

  const report = {
    generatedAt: new Date().toISOString(),
    baselineDate: budget.baselineDate,
    totals,
    counts: { all: assets.length, js: js.length, css: css.length, html: html.length },
    largestJs,
    echartsChunks,
    authJourneyChunks,
    careerGraphChunks,
    careerGraphCss,
    profileEvidenceChunks,
    profileEvidenceCss,
    matchTensionChunks,
    matchTensionCss,
    personalityFingerprintChunks,
    personalityFingerprintCss,
    reportPathChunks,
    reportPathCss,
    jobConstellationChunks,
    jobConstellationCss,
    homeWorkflowExperienceChunks,
    homeWorkflowExperienceCss,
    baseJsBytes,
    homepageInitial,
    limits: budget.limits,
    targets: budget.targets
  }

  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')

  console.log('PathFy frontend bundle report')
  console.log(`  Public: ${formatBytes(totals.publicBytes)} (${formatBytes(totals.publicGzipBytes)} gzip aggregate)`)
  console.log(`  JS:     ${formatBytes(totals.jsBytes)} (${formatBytes(totals.jsGzipBytes)} gzip aggregate)`)
  console.log(`  CSS:    ${formatBytes(totals.cssBytes)} (${formatBytes(totals.cssGzipBytes)} gzip aggregate)`)
  console.log(`  HTML:   ${formatBytes(totals.htmlBytes)} (${formatBytes(totals.htmlGzipBytes)} gzip aggregate)`)
  console.log('  Largest JavaScript chunks:')
  for (const item of largestJs) {
    console.log(`    ${item.file}: ${formatBytes(item.bytes)} (${formatBytes(item.gzipBytes)} gzip)`)
  }
  console.log(`  Homepage initial: ${formatBytes(homepageInitial.bytes)} (${formatBytes(homepageInitial.gzipBytes)} gzip, ${homepageInitial.files.length} files)`)
  console.log(`  Homepage ECharts: ${homepageInitial.loadsEcharts ? 'LOADED' : 'not loaded'}`)
  console.log(`  Auth journey lazy chunks: ${formatBytes(authJourneyBytes)} (${formatBytes(authJourneyGzipBytes)} gzip, ${authJourneyChunks.length} files)`)
  console.log(`  Homepage auth journey: ${homepageInitial.loadsAuthJourney ? 'LOADED' : 'not loaded'}`)
  console.log(`  Career graph route JS: ${formatBytes(sum(careerGraphChunks, 'bytes'))} (${formatBytes(sum(careerGraphChunks, 'gzipBytes'))} gzip, ${careerGraphChunks.length} files)`)
  console.log(`  Career graph route CSS: ${formatBytes(sum(careerGraphCss, 'bytes'))} (${formatBytes(sum(careerGraphCss, 'gzipBytes'))} gzip)`)
  console.log(`  Homepage career graph: ${homepageCareerGraph.length ? 'LOADED' : 'not loaded'}`)
  console.log(`  Profile evidence route JS: ${formatBytes(sum(profileEvidenceChunks, 'bytes'))} (${formatBytes(sum(profileEvidenceChunks, 'gzipBytes'))} gzip, ${profileEvidenceChunks.length} files)`)
  console.log(`  Profile evidence route CSS: ${formatBytes(sum(profileEvidenceCss, 'bytes'))} (${formatBytes(sum(profileEvidenceCss, 'gzipBytes'))} gzip)`)
  console.log(`  Homepage profile evidence: ${homepageProfileEvidence.length ? 'LOADED' : 'not loaded'}`)
  console.log(`  Match tension route JS: ${formatBytes(sum(matchTensionChunks, 'bytes'))} (${formatBytes(sum(matchTensionChunks, 'gzipBytes'))} gzip, ${matchTensionChunks.length} files)`)
  console.log(`  Match tension route CSS: ${formatBytes(sum(matchTensionCss, 'bytes'))} (${formatBytes(sum(matchTensionCss, 'gzipBytes'))} gzip)`)
  console.log(`  Homepage match tension: ${homepageMatchTension.length ? 'LOADED' : 'not loaded'}`)
  console.log(`  Personality fingerprint route JS: ${formatBytes(sum(personalityFingerprintChunks, 'bytes'))} (${formatBytes(sum(personalityFingerprintChunks, 'gzipBytes'))} gzip, ${personalityFingerprintChunks.length} files)`)
  console.log(`  Personality fingerprint route CSS: ${formatBytes(sum(personalityFingerprintCss, 'bytes'))} (${formatBytes(sum(personalityFingerprintCss, 'gzipBytes'))} gzip)`)
  console.log(`  Homepage personality fingerprint: ${homepagePersonalityFingerprint.length ? 'LOADED' : 'not loaded'}`)
  console.log(`  Report path route JS: ${formatBytes(sum(reportPathChunks, 'bytes'))} (${formatBytes(sum(reportPathChunks, 'gzipBytes'))} gzip, ${reportPathChunks.length} files)`)
  console.log(`  Report path route CSS: ${formatBytes(sum(reportPathCss, 'bytes'))} (${formatBytes(sum(reportPathCss, 'gzipBytes'))} gzip)`)
  console.log(`  Homepage report path: ${homepageReportPath.length ? 'LOADED' : 'not loaded'}`)
  console.log(`  Job constellation route JS: ${formatBytes(sum(jobConstellationChunks, 'bytes'))} (${formatBytes(sum(jobConstellationChunks, 'gzipBytes'))} gzip, ${jobConstellationChunks.length} files)`)
  console.log(`  Job constellation route CSS: ${formatBytes(sum(jobConstellationCss, 'bytes'))} (${formatBytes(sum(jobConstellationCss, 'gzipBytes'))} gzip)`)
  console.log(`  Homepage job constellation: ${homepageJobConstellation.length ? 'LOADED' : 'not loaded'}`)
  console.log(`  Home workflow experience JS: ${formatBytes(sum(homeWorkflowExperienceChunks, 'bytes'))} (${formatBytes(sum(homeWorkflowExperienceChunks, 'gzipBytes'))} gzip, ${homeWorkflowExperienceChunks.length} files)`)
  console.log(`  Home workflow experience CSS: ${formatBytes(sum(homeWorkflowExperienceCss, 'bytes'))} (${formatBytes(sum(homeWorkflowExperienceCss, 'gzipBytes'))} gzip)`)
  console.log(`  Homepage initial workflow experience: ${homepageWorkflowExperience.length ? 'LOADED' : 'not loaded'}`)
  console.log(`  JSON: ${relative(root, reportPath).replaceAll('\\', '/')}`)

  if (!shouldCheck) return

  const comparisons = [
    ['totalJsBytes', totals.jsBytes, budget.limits.totalJsBytes],
    ['baseJsBytes', baseJsBytes, budget.limits.baseJsBytes],
    ['totalCssBytes', totals.cssBytes, budget.limits.totalCssBytes],
    ['largestJsChunkBytes', totals.largestJsChunkBytes, budget.limits.largestJsChunkBytes],
    ['totalPublicBytes', totals.publicBytes, budget.limits.totalPublicBytes],
    ['authJourneyChunkBytes', authJourneyBytes, budget.limits.authJourneyChunkBytes],
    ['authJourneyChunkGzipBytes', authJourneyGzipBytes, budget.limits.authJourneyChunkGzipBytes],
    ['authJourneyChunkCount', authJourneyChunks.length, budget.limits.authJourneyChunkCount],
    ['careerGraphChunkBytes', sum(careerGraphChunks, 'bytes'), budget.limits.careerGraphChunkBytes],
    ['careerGraphChunkGzipBytes', sum(careerGraphChunks, 'gzipBytes'), budget.limits.careerGraphChunkGzipBytes],
    ['careerGraphChunkCount', careerGraphChunks.length, budget.limits.careerGraphChunkCount],
    ['careerGraphCssBytes', sum(careerGraphCss, 'bytes'), budget.limits.careerGraphCssBytes],
    ['careerGraphCssGzipBytes', sum(careerGraphCss, 'gzipBytes'), budget.limits.careerGraphCssGzipBytes],
    ['profileEvidenceChunkBytes', sum(profileEvidenceChunks, 'bytes'), budget.limits.profileEvidenceChunkBytes],
    ['profileEvidenceChunkGzipBytes', sum(profileEvidenceChunks, 'gzipBytes'), budget.limits.profileEvidenceChunkGzipBytes],
    ['profileEvidenceChunkCount', profileEvidenceChunks.length, budget.limits.profileEvidenceChunkCount],
    ['profileEvidenceCssBytes', sum(profileEvidenceCss, 'bytes'), budget.limits.profileEvidenceCssBytes],
    ['profileEvidenceCssGzipBytes', sum(profileEvidenceCss, 'gzipBytes'), budget.limits.profileEvidenceCssGzipBytes],
    ['matchTensionChunkBytes', sum(matchTensionChunks, 'bytes'), budget.limits.matchTensionChunkBytes],
    ['matchTensionChunkGzipBytes', sum(matchTensionChunks, 'gzipBytes'), budget.limits.matchTensionChunkGzipBytes],
    ['matchTensionChunkCount', matchTensionChunks.length, budget.limits.matchTensionChunkCount],
    ['matchTensionCssBytes', sum(matchTensionCss, 'bytes'), budget.limits.matchTensionCssBytes],
    ['matchTensionCssGzipBytes', sum(matchTensionCss, 'gzipBytes'), budget.limits.matchTensionCssGzipBytes],
    ['personalityFingerprintChunkBytes', sum(personalityFingerprintChunks, 'bytes'), budget.limits.personalityFingerprintChunkBytes],
    ['personalityFingerprintChunkGzipBytes', sum(personalityFingerprintChunks, 'gzipBytes'), budget.limits.personalityFingerprintChunkGzipBytes],
    ['personalityFingerprintChunkCount', personalityFingerprintChunks.length, budget.limits.personalityFingerprintChunkCount],
    ['personalityFingerprintCssBytes', sum(personalityFingerprintCss, 'bytes'), budget.limits.personalityFingerprintCssBytes],
    ['personalityFingerprintCssGzipBytes', sum(personalityFingerprintCss, 'gzipBytes'), budget.limits.personalityFingerprintCssGzipBytes],
    ['reportPathChunkBytes', sum(reportPathChunks, 'bytes'), budget.limits.reportPathChunkBytes],
    ['reportPathChunkGzipBytes', sum(reportPathChunks, 'gzipBytes'), budget.limits.reportPathChunkGzipBytes],
    ['reportPathChunkCount', reportPathChunks.length, budget.limits.reportPathChunkCount],
    ['reportPathCssBytes', sum(reportPathCss, 'bytes'), budget.limits.reportPathCssBytes],
    ['reportPathCssGzipBytes', sum(reportPathCss, 'gzipBytes'), budget.limits.reportPathCssGzipBytes],
    ['jobConstellationChunkBytes', sum(jobConstellationChunks, 'bytes'), budget.limits.jobConstellationChunkBytes],
    ['jobConstellationChunkGzipBytes', sum(jobConstellationChunks, 'gzipBytes'), budget.limits.jobConstellationChunkGzipBytes],
    ['jobConstellationChunkCount', jobConstellationChunks.length, budget.limits.jobConstellationChunkCount],
    ['jobConstellationCssBytes', sum(jobConstellationCss, 'bytes'), budget.limits.jobConstellationCssBytes],
    ['jobConstellationCssGzipBytes', sum(jobConstellationCss, 'gzipBytes'), budget.limits.jobConstellationCssGzipBytes],
    ['homeWorkflowExperienceChunkBytes', sum(homeWorkflowExperienceChunks, 'bytes'), budget.limits.homeWorkflowExperienceChunkBytes],
    ['homeWorkflowExperienceChunkGzipBytes', sum(homeWorkflowExperienceChunks, 'gzipBytes'), budget.limits.homeWorkflowExperienceChunkGzipBytes],
    ['homeWorkflowExperienceChunkCount', homeWorkflowExperienceChunks.length, budget.limits.homeWorkflowExperienceChunkCount],
    ['homeWorkflowExperienceCssBytes', sum(homeWorkflowExperienceCss, 'bytes'), budget.limits.homeWorkflowExperienceCssBytes],
    ['homeWorkflowExperienceCssGzipBytes', sum(homeWorkflowExperienceCss, 'gzipBytes'), budget.limits.homeWorkflowExperienceCssGzipBytes],
    ['homepageInitialGzipBytes', homepageInitial.gzipBytes, budget.targets.homepageInitialGzipBytes]
  ].filter(([, , limit]) => Number.isFinite(limit))
  const failures = comparisons.filter(([, actual, limit]) => actual > limit)
  if (homepageInitial.loadsEcharts) failures.push(['homepageEchartsChunks', homepageEcharts.length, 0])
  if (homepageInitial.loadsAuthJourney) failures.push(['homepageAuthJourneyChunks', homepageAuthJourney.length, 0])
  if (homepageCareerGraph.length) failures.push(['homepageCareerGraphChunks', homepageCareerGraph.length, 0])
  if (homepageProfileEvidence.length) failures.push(['homepageProfileEvidenceChunks', homepageProfileEvidence.length, 0])
  if (homepageMatchTension.length) failures.push(['homepageMatchTensionChunks', homepageMatchTension.length, 0])
  if (homepagePersonalityFingerprint.length) failures.push(['homepagePersonalityFingerprintChunks', homepagePersonalityFingerprint.length, 0])
  if (homepageReportPath.length) failures.push(['homepageReportPathChunks', homepageReportPath.length, 0])
  if (homepageJobConstellation.length) failures.push(['homepageJobConstellationChunks', homepageJobConstellation.length, 0])
  if (homepageWorkflowExperience.length) failures.push(['homepageWorkflowExperienceChunks', homepageWorkflowExperience.length, 0])
  if (authJourneyChunks.length === 0) failures.push(['authJourneyChunksMissing', 1, 0])
  if (careerGraphChunks.length === 0) failures.push(['careerGraphChunksMissing', 1, 0])
  if (profileEvidenceChunks.length === 0) failures.push(['profileEvidenceChunksMissing', 1, 0])
  if (matchTensionChunks.length === 0) failures.push(['matchTensionChunksMissing', 1, 0])
  if (personalityFingerprintChunks.length === 0) failures.push(['personalityFingerprintChunksMissing', 1, 0])
  if (reportPathChunks.length === 0) failures.push(['reportPathChunksMissing', 1, 0])
  if (jobConstellationChunks.length === 0) failures.push(['jobConstellationChunksMissing', 1, 0])
  if (homeWorkflowExperienceChunks.length === 0) failures.push(['homeWorkflowExperienceChunksMissing', 1, 0])
  if (failures.length) {
    for (const [name, actual, limit] of failures) {
      console.error(`Budget exceeded: ${name} ${formatBytes(actual)} > ${formatBytes(limit)}`)
    }
    process.exitCode = 1
  } else {
    console.log('  Budget check: PASS')
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  process.exitCode = 1
})
