// Proves the frontend tests are effective: each mutation breaks ONE behaviour of the sentiment feature in memory (no file on disk is touched) and at least one test must fail.
//
//     npm run test:mutations
//
// A mutation that is not detected ("SURVIVED") means a behaviour is not really protected; a mutation whose target text is not found ("NOT APPLIED") means this list is stale. Both fail the
// check. The unmutated control runs first and must pass, otherwise a failing mutation would prove nothing.
import { spawnSync } from "node:child_process"
import { readFileSync } from "node:fs"

const S = "src/lib/user-text-input.ts"
const C = "src/components/financial-health/behaviour-sentiment.tsx"
const H = "src/hooks/use-personalized-insight.ts"
const A = "src/lib/api-client.ts"
const P = "src/pages/financial-health-page.tsx"
const F = "src/lib/profile-form.ts"
const PB = "src/pages/financial-behaviour-page.tsx"
const SL = "src/lib/behaviour-summary.ts"
const SC = "src/components/financial-health/behaviour-summary-card.tsx"
const APP = "src/App.tsx"
const NAV = "src/components/shell/nav-items.ts"
const SB = "src/components/shell/app-sidebar.tsx"
const U = "src/pages/create-user-page.tsx"
const SSC = "src/components/security/security-status-card.tsx"
const SSP = "src/pages/security-status-page.tsx"
const SSH = "src/hooks/use-security-status.ts"
const SSL = "src/lib/security-status-labels.ts"
const VW = "src/components/financial-health/behaviour-sentiment-view.tsx"
const IP = "src/components/financial-health/behaviour-insights-panel.tsx"
const IN = "src/components/financial-health/sentiment-input-panel.tsx"
const RP = "src/components/financial-health/sentiment-results-panel.tsx"
const RA = "src/components/financial-health/risk-assessment-panel.tsx"
const BI = "src/lib/behaviour-insights.ts"
const LFM = "src/components/login-form.tsx"
const DCU = "src/lib/demo-customer.ts"
const MR = "src/hooks/use-monthly-records.ts"
const SF = "src/components/financial-health/spending-from-records.tsx"
const IF = "src/components/financial-health/individual-finances.tsx"
const FH = "src/pages/financial-health-page.tsx"
const DM = "src/lib/demo-mode.ts"
const DV = "src/components/financial-health/demo-financial-behaviour.tsx"
const DHK = "src/hooks/use-demo-financial-behaviour.ts"
const PS = "src/lib/plain-sentiment.ts"
const IB = "src/lib/investment-behaviour.ts"
const SP = "src/lib/spending-pattern.ts"
const BO = "src/lib/behaviour-overview.ts"
const TRL = "src/lib/transformer-research.ts"
const TRP = "src/components/financial-health/transformer-research-panel.tsx"
const BSEC = "src/components/financial-health/behaviour-sections.tsx"
const DFB = "src/components/financial-health/demo-family-behaviour.tsx"
const FBR = "src/components/financial-health/financial-behaviour-real.tsx"

// [id, what it breaks, file, find, replace, which runners may catch it]
const MUTATIONS = [
  ["L1", "limit no longer matches the backend", S, "export const MAX_USER_TEXT_CHARS = 1000", "export const MAX_USER_TEXT_CHARS = 2000", "pure"],
  ["L2", "DEL no longer refused", S, "\\u000e-\\u001f\\u007f", "\\u000e-\\u001f", "pure"],
  ["L3", "emoji counted as two characters", S, "return Array.from(text).length", "return text.length", "pure"],
  ["L4", "blank input sent as an empty string, not as no text", S, 'text: trimmed === "" ? null : trimmed', "text: trimmed", "pure"],
  ["L5", "duplicate submit while pending allowed", S, "if (pending) return { state, refetch: false, rejected: true }", "if (false) return { state, refetch: false, rejected: true }", "pure"],
  ["L6", "uncertain labelled Neutral", S, 'label: "Uncertain"', 'label: "Neutral"', "pure"],
  ["L7", "missing confidence shown as 0", S, 'if (confidence === null || confidence === undefined) return "Not available"', 'if (confidence === null || confidence === undefined) return "0"', "pure"],
  ["L8", "same text submitted again does not refetch", S, "refetch: checked.text === state.submitted", "refetch: false", "pure"],
  ["L9", "results never reported stale", S, "return draftText !== state.submitted", "return false", "pure"],
  ["L10", "text not trimmed", S, "const trimmed = raw.trim()", "const trimmed = raw", "pure"],
  ["L11", "control characters accepted", S, "if (CONTROL_CHARACTERS.test(raw)) {", "if (false) {", "pure"],
  ["L12", "over-long text accepted", S, "if (countCharacters(raw) > MAX_USER_TEXT_CHARS) {", "if (false) {", "pure"],
  ["L13", "invalid draft submitted anyway", S, "if (!checked.ok) return { state, refetch: false, rejected: true }", "if (false) return { state, refetch: false, rejected: true }", "pure"],
  ["L14", "clear keeps the submitted text", S, "return INITIAL_INPUT_STATE\n}", "return { draft: \"\", submitted: \"kept\" }\n}", "pure"],
  ["C1", "loading state never shown", C, "loading={insight.isLoading}", "loading={false}", "component"],
  ["C2", "backend response not passed to the view", C, "data={insight.data}", "data={undefined}", "component"],
  ["H1", "response kept in the cache after use", H, "gcTime: 0", "gcTime: 300000", "pure"],
  ["H2", "text removed from the query key (stale answers across texts)", H, 'queryKey: ["personalized-insight", profileId, text]', 'queryKey: ["personalized-insight", profileId]', "both"],
  ["H3", "failed request retried automatically", H, "retry: false", "retry: 3", "pure"],
  ["A1", "blank sent as an empty string", A, "body: JSON.stringify({ text }),", 'body: JSON.stringify({ text: text ?? "" }),', "pure"],
  ["A2", "wrong route", A, "/personalized-insights`", "/personalised-insights`", "pure"],
  ["A3", "text sent in the URL", A, "/personalized-insights`", "/personalized-insights?text=${text}`", "pure"],
  ["F1", "age upper limit no longer matches the backend", F, "ageMax: 120", "ageMax: 250", "pure"],
  ["F2", "an empty name is accepted", F, 'if (name === "") errors.name = "Enter your full name."', 'if (false) errors.name = "Enter your full name."', "pure"],
  ["F3", "a negative income is accepted", F, "if (!Number.isFinite(parsed) || parsed < 0)", "if (!Number.isFinite(parsed))", "pure"],
  ["F4", "an empty income is sent as zero", F, "payload: { name, age, income,", "payload: { name, age, income: income ?? 0,", "pure"],
  ["F5", "a fractional age is accepted", F, "!/^\\d{1,3}$/.test(ageText)", "!/^[\\d.]{1,5}$/.test(ageText)", "pure"],
  ["F6", "focus is not moved to the first invalid field", U, "document.getElementById(FIELD_IDS[checked.firstInvalid])?.focus()", "void 0", "pure"],
  ["F7", "the page stops using the validation rules", U, "if (!checked.ok) {", "if (false) {", "pure"],
  ["P3", "Financial Health keeps the detailed text card again", P, 'import { BehaviourSummaryCard } from "@/components/financial-health/behaviour-summary-card"', 'import { BehaviourSentimentCard } from "@/components/financial-health/behaviour-sentiment"', "pure"],
  ["P4", "Financial Health summary not keyed by profile", P, "<BehaviourSummaryCard key={profileId} profileId={profileId} />", "<BehaviourSummaryCard profileId={profileId} />", "pure"],
  ["R1", "route to the new page removed", APP, '          <Route path="financial-behaviour" element={<FinancialBehaviourPage />} />\n', "", "pure"],
  ["N1", "navigation entry removed", NAV, '      { title: "Behaviour & Sentiment", url: "/financial-behaviour", icon: MessageSquareText },\n', "", "pure"],
  ["S1", "summary shows far more than three facts", SL, "SUMMARY_MAX_FACTS = 3", "SUMMARY_MAX_FACTS = 99", "both"],
  ["S2", "summary repeats the bare month-count line", SL, 's.kind === "behaviour_fact" && !isMonthCount(s)', 's.kind === "behaviour_fact"', "both"],
  ["S3", "summary link points at the wrong page", SL, 'BEHAVIOUR_PAGE_PATH = "/financial-behaviour"', 'BEHAVIOUR_PAGE_PATH = "/financial-health"', "both"],
  ["S4", "summary sends text to the backend", SC, "usePersonalizedInsightQuery(profileId, null)", 'usePersonalizedInsightQuery(profileId, "x")', "pure"],
  ["S5", "summary link exposed to assistive technology as a button", SC, '<Link to={BEHAVIOUR_PAGE_PATH} className=', '<Link to={BEHAVIOUR_PAGE_PATH} role="button" className=', "both"],
  ["M1", "phone sidebar sheet stays open after choosing a page", SB, "onClick={closeMobileSheet}", "", "pure"],
  ["M2", "closing the phone sheet does nothing", SB, "const closeMobileSheet = () => setOpenMobile(false)", "const closeMobileSheet = () => {}", "pure"],
  ["S9", "summary link text no longer describes the destination", SC, "Open Financial Behaviour &amp; Sentiment <ArrowRight", "Click here <ArrowRight", "component"],
  ["S7", "summary shows no error state", SC, "{error ? (", "{false ? (", "component"],
  ["S8", "summary shows no loading state", SC, "loading && !data ?", "false ?", "component"],
  // Data Protection page (ADR-047)
  ["D1", "security page not keyed by profile (earlier result survives a switch)", SSP, "<SecurityStatusCard key={profileId} profileId={profileId} />", "<SecurityStatusCard profileId={profileId} />", "pure"],
  ["D2", "route to the security page removed", APP, '          <Route path="security" element={<SecurityStatusPage />} />\n', "", "pure"],
  ["D3", "navigation entry for the security page removed", NAV, '      { title: "Data Protection", url: "/security", icon: ShieldCheck },\n', "", "pure"],
  ["D4", "security status served from a 60 s cache", SSH, "staleTime: 0", "staleTime: 60000", "pure"],
  ["D5", "security status kept in the cache after unmount", SSH, "gcTime: 0", "gcTime: 300000", "pure"],
  ["D6", "security status silently retried", SSH, "retry: false", "retry: 3", "pure"],
  ["D7", "security query runs without a profile", SSH, "enabled: profileId !== null", "enabled: true", "pure"],
  ["D8", "security client call loses the identity header", A, "      headers: asCustomer(profileId),", "", "pure"],
  ["D9", "page claims the audit trail is decentralized", SSC, "It is not decentralized, has no consensus, and is not independently tamper-proof.", "It is decentralized and immutable.", "both"],
  ["D10", "failed chain verification labelled consistent", SSL, 'invalid: "Verification failed",', 'invalid: "Internally consistent",', "component"],
  ["D11", "empty chain labelled consistent", SSL, 'empty: "No events recorded yet",', 'empty: "Internally consistent",', "component"],
  ["D12", "failed self-test labelled operating", SSL, 'failed: "Self-test failed",', 'failed: "Operating",', "component"],
  ["D13", "prototype label replaced", SSC, "<AlertTitle>{data.prototype_notice}</AlertTitle>", "<AlertTitle>Blockchain-secured</AlertTitle>", "component"],
  ["D14", "existing-data warning removed", SSC, "<CardTitle>Existing data is not encrypted</CardTitle>", "<CardTitle>Existing data</CardTitle>", "component"],
  ["D15", "earlier result shown beside an error", SSC, "if (error) return <ErrorState error={error} onRetry={onRetry} />", "if (error && !data) return <ErrorState error={error} onRetry={onRetry} />", "component"],
  ["D16", "self-test line shown when there was no key", SSC, '{encryption.self_test_passed === null ? null : <p>Self-test: {encryption.self_test_passed ? "passed" : "failed"}</p>}', '<p>Self-test: {encryption.self_test_passed ? "passed" : "failed"}</p>', "component"],
  ["D17", "failing event number hidden", SSC, "{ledger.first_invalid_sequence !== null ? <p>First failing event: #{ledger.first_invalid_sequence}</p> : null}", "{null}", "component"],
  ["D18", "limitations hidden", SSC, "{data.limitations.map((limitation) => (", "{[].map((limitation: string) => (", "component"],
  ["D19", "no loading state", SSC, "if (loading && !data) return <LoadingState", "if (false) return <LoadingState", "component"],
  ["D20", "unprotected categories hidden", SSC, "{existing.unprotected_categories.map((category) => (", "{[].map((category: string) => (", "component"],
  ["D22", "a 503 is shown as a generic failed analysis", SSC, "error.problem.status === 503", "error.problem.status === 0", "component"],
  ["D23", "the 503 sentence from the backend is replaced by a fixed one", SSC, "<p>{error.problem.detail}</p>", "<p>Something went wrong.</p>", "component"],
  ["D21", "external ledger shown as connected", SSC, '<p className="text-muted-foreground">{anchor.detail}</p>', '<p className="text-muted-foreground">Connected</p>', "component"],

  ["S6", "summary hides that more findings exist", SC, '{summary.moreFacts ? <p className="text-muted-foreground text-xs">More findings are on the full page.</p> : null}', "{null}", "component"],
  // Redesigned Financial Behaviour & Sentiment page (ADR-048)
  ["V1", "a failed request shown beside the earlier results", VW, "            ) : data ? (\n              plainLanguage ? (", "            ) : null}\n            {data ? (\n              plainLanguage ? (", "component"],
  ["V1b", "records and assessment still shown after a failed request", VW, "{error ? (", "{false ? (", "component"],
  ["V2", "stale-results notice removed", VW, "{stale && data && !error ? (", "{false ? (", "component"],
  ["V3", "a missing text rendered as a reading", RP, 'status.kind === "no_text" ? (', 'status.kind === "never" ? (', "component"],
  ["V4", "results region not live", VW, 'aria-live="polite" aria-busy={pending || loading}', "aria-busy={pending || loading}", "component"],
  ["V5", "validation message not announced", IN, '<p id="insight-text-error" role="alert" className="text-destructive text-sm">', '<p id="insight-text-error" className="text-destructive text-sm">', "component"],
  ["V6", "label not tied to the text area", IN, '<Label htmlFor="insight-text">', '<Label htmlFor="insight-txt">', "component"],
  ["V7", "missing confidence displayed as 0", RP, "describeConfidence(sentiment.confidence, sentiment.confidence_band)", "describeConfidence(sentiment.confidence ?? 0, sentiment.confidence_band)", "component"],
  ["V8", "conflict not shown", RP, "<Conflicts conflicts={data.conflicts} />", "{null}", "component"],
  // The multi-stage interpretation (ADR-050)
  ["N1", "the informational-only notice is dropped", RP, "<AlertDescription>{INFORMATIONAL_NOTICE}</AlertDescription>", "<AlertDescription>{''}</AlertDescription>", "component"],
  ["N2", "an abstention is presented as a reading", S, 'if (reading.abstained || reading.interpretation_state === "abstained") {', "if (false) {", "pure"],
  ["N3", "a weak or unknown state is promoted to valid", S, 'if (reading.interpretation_state !== "valid") {', "if (false) {", "pure"],
  ["N4", "the fallback to the rules baseline is not announced", RP, "{status.fallback ? (", "{false ? (", "component"],
  ["N5", "the unconfirmed-interpretation notice is dropped", RP, '<p className="text-sm">{PREFERENCE_NOTICE}</p>', "{null}", "component"],
  ["N6", "the conflict stops saying the stored assessment is authoritative", RP, "(remains authoritative; source: {conflict.authoritative_source})", "(source: {conflict.authoritative_source})", "component"],
  ["N7", "the risk panel stops saying the assessment remains authoritative", RA, '{data.risk_profile.remains_authoritative ? <Badge variant="outline">Remains authoritative</Badge> : null}', "{null}", "component"],
  ["N8", "insufficient evidence is worded as neutral", S, 'label: "Not enough evidence"', 'label: "Neutral"', "pure"],
  ["N9", "an unrelated text gets the general message", S, 'reading.abstain_reason === "unrelated_text"', 'reading.abstain_reason === "never"', "pure"],
  ["N10", "the rules baseline is worded as a model", S, 'rules_baseline: "Rules baseline (a small fixed set of rules, not a trained model)"', 'rules_baseline: "Model"', "pure"],
  ["N11", "the validation status is hidden", RP, '<dd>{validationLabel(sentiment.validation_status)}</dd>', "<dd>{''}</dd>", "component"],
  ["N12", "the emotional tone is shown without its risk-tolerance disclaimer", RP, "this is not a measure of how much risk you can take", "this is a measure of how much risk you can take", "component"],
  ["V9", "preferences shown as confirmed", RP, "                    Unconfirmed\n", "                    Confirmed\n", "component"],
  ["V10", "Clear always enabled", IN, 'disabled={pending || (draft === "" && !hasSubmittedText)}', "disabled={pending}", "component"],
  ["V11", "Analyse enabled while pending or invalid", IN, "const submitDisabled = pending || invalid", "const submitDisabled = false", "component"],
  ["V12", "pending state not shown on the button", IN, '{pending ? "Analysing…" : "Analyse"}', '{"Analyse"}', "component"],
  ["V13", "form loses its accessible name", IN, 'aria-label="Optional text about your finances"', "", "component"],
  ["V14", "long evidence no longer wraps", RP, "[overflow-wrap:anywhere]", "", "component"],
  ["V15", "evidence truncated to a fragment", RP, "&ldquo;{children}&rdquo;", "&ldquo;{children.slice(0, 5)}&rdquo;", "component"],
  ["V16", "insight rows repeated", IP, "{rows.map((row) => (", "{[...rows, ...rows].map((row) => (", "component"],
  ["V17", "counter shows a different limit", IN, "{used} / {MAX_USER_TEXT_CHARS} characters", "{used} / 500 characters", "component"],
  ["V18", "rules baseline presented as a validated model", RP, "A simple automatic reading, not a validated model", "A validated model reading", "component"],
  ["V19", "backend limitations hidden", RP, "{sentiment.limitations.length > 0 ? (", "{false ? (", "component"],
  ["V20", "risk assessment fallback removed", RA, "No risk assessment is on file for this profile yet. Nothing is assumed in its place.", "", "component"],
  ["V21", "text area replaced by a single-line input", IN, 'import { Textarea } from "@/components/ui/textarea"', 'import { Input as Textarea } from "@/components/ui/input"', "both"],
  ["V22", "hard length cap added to the text area", IN, 'className="min-h-32 resize-y"', 'className="min-h-32 resize-y" maxLength={1000}', "both"],
  ["V23", "Ctrl+Enter shortcut removed from the text area", IN, "if (isSubmitShortcut(event.nativeEvent)) {", "if (false) {", "pure"],
  ["V24", "any Ctrl or Cmd key submits on Enter, plus a plain Enter", S, 'event.key === "Enter" && (event.ctrlKey || event.metaKey) &&', "event.key === \"Enter\" &&", "pure"],
  ["V25", "Enter without a modifier counts as the shortcut via a loosened check", S, "(event.ctrlKey || event.metaKey) &&", "(event.ctrlKey || event.metaKey || event.shiftKey) &&", "pure"],
  ["V26", "unavailable and not-included findings shown as insights", BI, 'f.status === "observed" && !isMonthCount(f)', "!isMonthCount(f)", "both"],
  ["V27", "the bare month count repeated as an insight row", BI, 'f.status === "observed" && !isMonthCount(f)', 'f.status === "observed"', "both"],
  ["V28", "direction dropped from an insight", BI, "direction: f.direction ?? null,", "direction: null,", "both"],
  ["V29", "an uncertain reading is not flagged inconclusive", S, 'This is not the same as neutral.", icon: "uncertain", inconclusive: true }', 'This is not the same as neutral.", icon: "uncertain", inconclusive: false }', "both"],
  ["V30", "an inconclusive reading styled like a found one", RP, 'presentation.inconclusive ? "text-muted-foreground border-dashed" : "bg-muted/40"', '"bg-muted/40"', "component"],
  ["V31", "the 'Not a confirmed reading' marker removed", RP, '{presentation.inconclusive ? <p className="text-xs">Not a confirmed reading.</p> : null}', "{null}", "component"],
  ["V32", "the stored assessment's authority is not stated on a conflict", RP, "<p>Your existing risk assessment stays the authority. Your words do not change it.</p>", "", "component"],
  ["V33", "the assessment panel says it is updated from the words", RA, "Kept separate from the reading of your words. Your words never change it.", "Updated from the reading of your words.", "component"],
  ["V34", "the view repeats the page title", VW, "      {records ? <Intro /> : null}\n", "      <h1>Financial Behaviour &amp; Sentiment</h1>\n      {records ? <Intro /> : null}\n", "both"],
  ["V35", "the two-column layout lost", VW, "lg:grid-cols-12", "", "component"],
  ["V36", "the text box column comes before the records column", VW, "lg:col-span-7", "lg:col-span-5", "component"],
  ["V37", "the intro that separates observed from expressed is removed", VW, "      {records ? <Intro /> : null}\n", "", "component"],
  ["V38", "the empty-state pointer to monthly records points nowhere", IP, 'to="/profile"', 'to="/nowhere"', "component"],
  ["V39", "an insight sentence is recomputed", IP, "const months = behaviour.observation_count", "const months = Math.round(behaviour.observation_count)", "pure"],
  ["V40", "the text is written to local storage", IN, "const checked = validateUserText(draft)", 'localStorage.setItem("insight", draft); const checked = validateUserText(draft)', "pure"],
  ["V41", "the text is logged", IN, "const used = countCharacters(draft)", "console.log(draft); const used = countCharacters(draft)", "pure"],
  ["V42", "Clear keeps the draft", C, "onClear={() => setInput(clearAll())}", 'onClear={() => setInput((current) => ({ ...current, submitted: null }))}', "pure"],
  ["V43", "a profile switch keeps the typed text and results", PB, "<FinancialBehaviourReal key={profileId} profileId={profileId} demoHint={demoHint} />", "<FinancialBehaviourReal profileId={profileId} demoHint={demoHint} />", "pure"],
  ["V44", "a second submit while pending allowed", C, "if (outcome.rejected) return", "if (false) return", "pure"],
  // Full-pipeline demo sign-in
  ["G1", "the sign-in entry is not offered", LFM, "Use Full Pipeline Demo", "Use Demo", "pure"],
  ["G2", "the persona name drifts from the backend package", DCU, 'FULL_PIPELINE_DEMO_NAME = "WealthPilot Demo \u2014 Full Pipeline"', 'FULL_PIPELINE_DEMO_NAME = "WealthPilot Demo \u2014 Pipeline"', "pure"],
  ["G3", "an unseeded environment gets a created customer instead of an error", DCU, "if (customer_id === null) throw new FullPipelineDemoNotSeededError()", "if (customer_id === null) return (await api.createProfile({ name: FULL_PIPELINE_DEMO_NAME })).customer_id", "pure"],
  ["G4", "the entry can be pressed again while a sign-in is resolving", LFM, "onClick={handlePipelineDemoLogin}\n              disabled={pendingAction !== null}", "onClick={handlePipelineDemoLogin}", "pure"],
  ["G5", "the unseeded message no longer names the seed command", LFM, "The full-pipeline demo has not been set up in this environment yet (seed_demo_data.py setup).", "Could not set up.", "pure"],
  ["G6", "the entry signs in without the demo credential gate", LFM, 'await attemptLogin(DEMO_EMAIL, DEMO_PASSWORD, "pipeline")', 'await completeLogin("pipeline")', "pure"],
  ["G7", "the home-page hint no longer reaches the new entry", LFM, 'if (demoHint === "pipeline") pipelineDemoRef.current?.focus()', "", "pure"],
  // Financial Health: spending from reported months, debt & commitments, cache refresh (ADR-051)
  ["H1", "a saved month no longer refreshes the behaviour and spending findings", MR, 'queryClient.invalidateQueries({ queryKey: ["personalized-insight", profileId] })', "", "pure"],
  ["H2", "the spending view shows every finding, not the spending ones", "src/lib/behaviour-insights.ts", "selectInsightRows(findings).filter((row) => SPENDING_FINDING_CODES.includes(row.code))", "selectInsightRows(findings)", "component"],
  ["H3", "a failed request is shown as 'no reported months'", SF, "if (error) return <ErrorState error={error} onRetry={onRetry} />", "", "component"],
  ["H4", "no reported months is not stated", SF, 'title="No reported months yet"', 'title=""', "component"],
  ["H5", "the spending card claims a category breakdown", SF, "so there is no category breakdown here", "so categories are shown here", "component"],
  ["H6", "the spending card is not keyed by profile", FH, "<SpendingFromRecords key={profileId} profileId={profileId} />", "<SpendingFromRecords profileId={profileId} />", "pure"],
  ["H7", "the commitments card is not keyed by profile", FH, "<CommitmentsCard key={profileId} profileId={profileId} />", "<CommitmentsCard profileId={profileId} />", "pure"],
  ["H8", "an individual's debt is shown as a missing value instead of an unsupported record", IF, 'title="Not recorded for an individual"', 'title="Not available"', "component"],
  ["H9", "a household member is no longer pointed to the household's liabilities", IF, "{householdName ? (", "{false ? (", "component"],
  // The trained model (ADR-052)
  ["T1", "a model that is not validated is called validated", S, 'return reading.validation_status === "validated"', "return true", "pure"],
  ["T2", "a fallback is presented as a model answer", S, "if (reading.fallback_used) return { kind: \"rules_fallback\"", "if (false) return { kind: \"rules_fallback\"", "pure"],
  ["T3", "a missing intensity is shown as 0", S, '"Not available: no validated intensity model"', '"0"', "pure"],
  ["T4", "the model unavailable (fallback off) is shown as a model answer", S, "if (reading.fallback_used && reading.abstained) return", "if (false) return", "pure"],
  ["T5", "a fallback reason loses its wording", S, 'FALLBACK_REASON_LABELS[code] ?? code.replace(/_/g, " ")', 'code.replace(/_/g, " ")', "pure"],
  ["T6", "the disagreement alert is dropped", RP, "{sentiment.disagreement ? (", "{false ? (", "component"],
  ["T7", "the class probabilities are not shown", RP, "{sentiment.class_probabilities ? (", "{false ? (", "component"],
  ["T8", "the rules reading is no longer kept beside a model reading", RP, "{sentiment.rules_baseline && (sentiment.method !== \"rules_baseline\" || sentiment.disagreement) ? (", "{false ? (", "component"],
  ["T9", "the method row is removed", RP, '<dd data-method={methodUsed.kind}>', '<dd data-method="x">{null}', "component"],
  ["T10", "the interpretation notice is dropped", RP, "<p className=\"text-muted-foreground text-xs\">{INTERPRETATION_NOTICE}</p>", "{null}", "component"],
  ["DM1", "demo mode honoured on a build that does not allow it", DM, "  if (!allowed) return false", "  if (false) return false", "pure"],
  ["DM2", "demo mode requested by any value of the query", DM, "return values.length === 1 && values[0] === DEMO_QUERY_VALUE", "return values.length >= 1", "pure"],
  ["DM3", "every build allows demo mode", DM, "return env.DEV === true || env.VITE_DEMO_MODE === \"true\"", "return true", "pure"],
  ["DM4", "the page shows demo data whenever the query is present, ignoring the build", PB, "  const { kind, problem } = demoRequest(search, allowDemo)\n  if (kind === \"family\") return <FinancialBehaviourFamilyDemoContent />\n  if (kind === \"individual\") return <FinancialBehaviourDemoContent />\n", "  const asked = new URLSearchParams(search).get(\"demo\")\n  const problem = null\n  if (asked === \"family\") return <FinancialBehaviourFamilyDemoContent />\n  if (asked === \"true\") return <FinancialBehaviourDemoContent />\n", "component"],
  ["DM5", "an unavailable change shown as zero", DV, "        {NOT_AVAILABLE}\n        {feature.unavailable_reason ?", "        {\"0.0%\"}\n        {feature.unavailable_reason ?", "component"],
  ["DM6", "a failed request still shows the demo months", DV, "  if (error) {\n    return (\n      <div className=\"space-y-6\">\n        <DemoBanner />", "  if (false) {\n    return (\n      <div className=\"space-y-6\">\n        <DemoBanner />", "component"],
  ["DM7", "a 404 from the demo route reads as a generic not-found", DV, "if (error instanceof ApiClientError && (isDemoDisabledProblem(error.problem.title) || error.problem.status === 404)) {", "if (false) {", "component"],
  ["DM8", "the demo banner is not announced as a status", DV, "<Alert role=\"status\" aria-label=\"Demonstration mode is active\"", "<Alert", "component"],
  ["DM9", "the months table loses its scrollable focusable region on a narrow screen", DV, "className=\"overflow-x-auto\" role=\"region\"", "className=\"\" role=\"region\"", "component"],
  ["DM10", "the method panel shows a confidence the backend did not give", DV, "sentiment.confidence === null || sentiment.confidence === undefined ? NOT_AVAILABLE : formatPercent(sentiment.confidence, 0)", "sentiment.confidence === null || sentiment.confidence === undefined ? \"0%\" : formatPercent(sentiment.confidence, 0)", "component"],
  ["DM11", "the demo query keeps a copy of the typed text after it is no longer observed", DHK, "gcTime: 0,", "gcTime: 300000,", "pure"],
  ["DM12", "the family sign-in discards the requested address", LFM, "navigate(destinationAfterLogin(\"family\", from), { replace: true })", "navigate(\"/profile?household=open\", { replace: true })", "pure"],
  ["DM13", "a weak (hypothetical or past-only) note is read as a current feeling", PS, "if (reading.interpretation_state === \"weak\" || reading.sentiment === \"uncertain\") return \"uncertain\"", "if (reading.sentiment === \"uncertain\") return \"uncertain\"", "pure"],
  ["DM14", "the model-disabled sentence is stated without the backend saying so", PS, "if (modelState === \"disabled\") notes.push(MODEL_DISABLED_NOTE)", "notes.push(MODEL_DISABLED_NOTE)", "pure"],
  ["DM15", "unusual investing is claimed without a model flag", IB, "if (driftFlag === true || anomalyFlag === true)", "if (driftFlag !== false || anomalyFlag !== false)", "pure"],
  ["DM16", "no investment history is reported as consistent", IB, "return result(\"not_enough_history\", NOT_ENOUGH_HISTORY_DETAIL,", "return result(\"consistent\", NOT_ENOUGH_HISTORY_DETAIL,", "pure"],
  ["DM17", "a backend outage is reported as a model problem", SP, "? { kind: \"backend_unavailable\"", "? { kind: \"model_unavailable\"", "pure"],
  ["DM18", "a spending pattern is shown without one from the model", SP, "if (input.persona) return { kind: \"valid\"", "if (input.persona || input.history === \"multiple_months\") return { kind: \"valid\"", "pure"],
  ["DM19", "an unavailable savings rate is read as zero", BO, "typeof finding.values?.ratio === \"number\" ? finding.values.ratio : null", "typeof finding.values?.ratio === \"number\" ? finding.values.ratio : 0", "pure"],
  ["DM20", "the date range does not sort the months", BO, "const sorted = [...periods].sort()", "const sorted = [...periods]", "pure"],
  ["DM21", "the family demonstration is honoured on a build that does not allow it", DM, "  if (!allowed) return null", "  if (false) return null", "pure"],
  ["DM22", "the technical reading is shown outside the optional details", VW, "{detailedReading(data, modelState, <SentimentResultsPanel data={data} />)}", "<SentimentResultsPanel data={data} />", "component"],
  ["DM23", "a family member loses the 'Not recorded for an individual' wording", DFB, "      <SectionUnavailable title={INDIVIDUAL_COMMITMENTS_TITLE} message={INDIVIDUAL_COMMITMENTS_MESSAGE} />\n", "", "component"],
  ["DM24", "an unavailable spending pattern is drawn as a result", BSEC, ") : state.kind === \"valid\" ? (", ") : state.kind !== \"loading\" ? (", "component"],
  ["DM25", "zero records no longer show the empty state", BSEC, "} else if (insight.behaviour.observation_count === 0) {", "} else if (false) {", "component"],
  ["DM26", "the optional-note statement is dropped", VW, "{plainLanguage ? <p className=\"text-sm\">{OPTIONAL_NOTE_STATEMENT}</p> : null}", "", "component"],
  ["DM27", "a demo parameter on a build that does not allow it is silently ignored", DM, "if (!allowed) return { kind: null, problem: \"not_allowed\" }", "if (!allowed) return { kind: null, problem: null }", "pure"],
  ["DM28", "the sidebar link drops the demonstration from inside it", DM, "return pathname === DEMO_PAGE_PATH && demoKind(search, allowed) !== null ? `${DEMO_PAGE_PATH}${search}` : DEMO_PAGE_PATH", "return DEMO_PAGE_PATH", "pure"],
  ["DM29", "the developer pointer to the fictional examples is shown to every profile", FBR, "{props.demoHint && insight && insight.behaviour.observation_count === 0 ? <DevDemoHint /> : null}", "{insight ? <DevDemoHint /> : null}", "component"],
  ["DM30", "the 'demonstration mode is not active' notice is not shown", PB, "      {demoProblem ? <DemoRequestNotice problem={demoProblem} /> : null}\n      <FinancialBehaviourReal", "      <FinancialBehaviourReal", "component"],
  ["DM31", "a sign-in from a protected address drops its query", DM, "if (from) return from.pathname + (from.search ?? \"\")", "if (from) return from.pathname", "pure"],
  ["DM32", "the family sign-in default loses the household section", DM, "return action === \"family\" ? \"/profile?household=open\" : \"/dashboard\"", "return \"/dashboard\"", "pure"],
  ["TR1", "the switched-off research state is reported as agreement", TRL, "if (!research.enabled) return \"switched_off\"", "if (!research.enabled) return \"models_agree\"", "component"],
  ["TR2", "an unknown label is shown as neutral", TRL, "return LABELS[label] ?? \"Unavailable\"", "return LABELS[label] ?? \"Neutral\"", "component"],
  ["TR3", "the important notices are not shown", TRP, "research.notices.map((notice) =>", "[].map((notice: string) =>", "component"],
  ["TR4", "the 'confidence is not available' explanation is dropped", TRP, "<p className=\"text-muted-foreground text-xs\">{NO_CONFIDENCE_TEXT}</p>", "", "component"],
  ["TR5", "agreement is worded as disagreement", TRL, "agreement: \"The two models agree\"", "agreement: \"The two models disagree\"", "component"],
  ["TR6", "the panel hides itself while the research models are off", TRP, "if (!research) return null", "if (!research || !research.enabled) return null", "component"],
  ["TR7", "the rules-based fallback is not labelled as a fallback", TRP, "{fellBack ? \" (the rules-based reading, used as the fallback)\" : \" (experimental)\"}", "{\" (experimental)\"}", "component"],
  ["TR8", "a disagreement is reported as agreement", TRL, "case \"disagreement\":\n      return \"models_disagree\"", "case \"disagreement\":\n      return \"models_agree\"", "component"],
  ["TR9", "the plain-language view omits the research panel", VW, "                  <TransformerResearchPanel research={data.transformer_research} />\n                </>\n              ) : (", "                </>\n              ) : (", "component"],
  ["TR10", "the full view omits the research panel", VW, "                  <SentimentResultsPanel data={data} />\n                  <TransformerResearchPanel research={data.transformer_research} />", "                  <SentimentResultsPanel data={data} />", "component"],
  ["TR11", "raw model scores are rounded in the browser", TRL, "value: String(value) }", "value: String(Math.round(value * 100) / 100) }", "component"],
  ["TR12", "an unavailable or loading model is shown with the answered badge", TRP, "const badge = available ? \"Answered\" : model.availability === \"loading\" ? \"Loading\" : \"Unavailable\"", "const badge = \"Answered\"", "component"],
  ["TR13", "an empty slot is shown as a failed model", TRP, "  if (isEmptySlot(model)) {", "  if (false) {", "component"],
  ["TR14", "a single model that differs from the rules reading is reported as agreeing", TRL, "return relation === \"agrees\" ? \"single_agrees\" : relation === \"disagrees\" ? \"single_differs\" : \"single_rules_abstained\"", "return \"single_agrees\"", "component"],
  ["TR15", "a model that is still loading is not announced", TRL, "  if (research.models.some((m) => m.availability === \"loading\")) return \"loading\"\n", "", "component"],
  ["TR16", "a slot whose approved model is awaiting registration is treated as a failure", TRL, " || model.unavailable_reason === \"registration_pending\"", "", "component"],
  ["TR17", "the per-model comparison with the rules reading is not shown", TRP, "{research.comparison.model_vs_rules.map((entry) => (", "{[].map((entry: { slot: string; model_label: string | null; rules_label: string | null }) => (", "component"],
  ["TR18", "an unexpected research problem is not reassured as harmless to the reading above", TRL, " Your reading above is not affected.", "", "component"],
]

// Node runs every test file in its own process, so each file is run separately: a file that never loads the mutated module exits 3 ("not applied") and says nothing about the mutation.
const RUNNERS = {
  pure: [
    ["--import", "./tests/mutate-hook.mjs", "--test", "tests/user-text-input.test.ts"],
    ["--import", "./tests/mutate-hook.mjs", "--test", "tests/profile-form.test.ts"],
    ["--import", "./tests/mutate-hook.mjs", "--test", "tests/behaviour-summary.test.ts"],
    ["--import", "./tests/mutate-hook.mjs", "--test", "tests/security-status.test.ts"],
    ["--import", "./tests/mutate-hook.mjs", "--test", "tests/behaviour-redesign.test.ts"],
    ["--import", "./tests/mutate-hook.mjs", "--test", "tests/demo-login.test.ts"],
    ["--import", "./tests/mutate-hook.mjs", "--test", "tests/demo-data-flow.test.ts"],
  ],
  component: [["--test", "tests/component.test.mjs"]],
}

function run(runner, mutation) {
  const env = { ...process.env }
  delete env.WP_MUTATION
  if (mutation) env.WP_MUTATION = JSON.stringify(mutation)
  const results = RUNNERS[runner].map((args) => {
    const result = spawnSync(process.execPath, args, { env, encoding: "utf8", timeout: 120_000 })
    return { code: result.status, out: `${result.stdout ?? ""}${result.stderr ?? ""}` }
  })
  const out = results.map((r) => r.out).join("\n")
  if (!mutation) return { code: results.every((r) => r.code === 0) ? 0 : 1, out }
  if (results.every((r) => r.code === 3)) return { code: 3, out: `MUTATION NOT APPLIED\n${out}` } // no file in this runner ever loaded the mutated module
  return { code: results.some((r) => r.code !== 0 && r.code !== 3) ? 1 : 0, out } // killed if a file that loaded it failed
}

// Pre-flight: a mutation whose target text no longer exists in its file is STALE. The loader throws on such a target while a test file is loading, and a thrown load looks exactly like a
// test failure, so without this check a stale mutation would be counted as "killed" and prove nothing. The text is compared exactly as the loader reads it (line endings included).
const stale = MUTATIONS.filter(([, , file, find]) => {
  try {
    return !readFileSync(file, "utf8").replace(/\r\n/g, "\n").includes(find)
  } catch {
    return true
  }
})
for (const [id, what, file] of stale) console.log(`${id.padEnd(4)} STALE (target text not found in ${file}) ${what}`)
if (stale.length > 0) {
  console.log(`\n${stale.length} stale mutation(s): the check FAILED before running anything`)
  process.exit(1)
}

let failed = false
for (const runner of ["pure", "component"]) {
  const control = run(runner)
  const ok = control.code === 0
  console.log(`control (${runner}, unmutated): ${ok ? "pass" : "FAIL"}`)
  if (!ok) {
    console.log(control.out.split("\n").slice(-25).join("\n"))
    process.exit(1)
  }
}

const rows = []
for (const [id, what, file, find, replace, where] of MUTATIONS) {
  const runners = where === "both" ? ["pure", "component"] : [where]
  let verdict = "SURVIVED"
  for (const runner of runners) {
    // a mutation in a file the "pure" runner never loads is applied by its hook only when that file is loaded; the page and API client are read as text by the pure tests, so they are mutated on read
    const { code } = run(runner, { file, find, replace })
    if (code === 3) {
      verdict = "NOT APPLIED"
      break
    }
    if (code !== 0) {
      verdict = `killed by ${runner}`
      break
    }
  }
  if (verdict.startsWith("SURVIVED") || verdict === "NOT APPLIED") failed = true
  rows.push([id, verdict, what])
}

for (const [id, verdict, what] of rows) console.log(`${id.padEnd(4)} ${verdict.padEnd(22)} ${what}`)
const killed = rows.filter((r) => r[1].startsWith("killed")).length
console.log(`\n${killed} of ${rows.length} mutations detected${failed ? "; the check FAILED (survivor or stale mutation)" : ""}`)
process.exit(failed ? 1 : 0)
