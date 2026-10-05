/**
 * The ONE place that turns internal/API values into plain-language labels
 * for a reader with no finance background (`docs/DESIGN.md` section 30).
 *
 * Presentation only. Every function here looks up a label for a value the
 * API already returned -- the value itself is never changed, re-derived or
 * sent back anywhere, and nothing here calculates. An unknown value always
 * falls back to the raw value (never hidden, never guessed). The technical
 * name of each term stays available for the "Technical details" sections, so
 * the primary UI can be plain while evaluators still see the real method,
 * ticker, rule and version.
 */

export interface TermInfo {
  /** Plain-language label for the primary UI. */
  label: string
  /** The technical name, shown only in "Technical details". */
  technical: string
  /** A short, factual, non-promotional explanation for a help tooltip. */
  help: string
}

// --- investments ------------------------------------------------------------

interface AssetInfo extends TermInfo {
  /** A shorter label for tight spaces (chart legends on phones). */
  short: string
}

const ASSETS: Record<string, AssetInfo> = {
  QQQ: {
    label: "Nasdaq-100 / US Growth",
    short: "US Growth",
    technical: "Ticker: QQQ",
    help: "Exposure to the large non-financial companies listed on the Nasdaq-100.",
  },
  AGG: {
    label: "US Bond Market",
    short: "US Bonds",
    technical: "Ticker: AGG",
    help: "Exposure to a diversified group of US bonds.",
  },
  GLD: {
    label: "Gold",
    short: "Gold",
    technical: "Ticker: GLD",
    help: "Exposure to the price of gold, used to diversify.",
  },
  "^NDX": {
    label: "Nasdaq-100 index",
    short: "Nasdaq-100",
    technical: "Ticker: ^NDX",
    help: "The market index of the 100 largest non-financial companies listed on the Nasdaq.",
  },
  "^IXIC": {
    label: "Nasdaq Composite index",
    short: "Nasdaq Composite",
    technical: "Ticker: ^IXIC",
    help: "The market index of the companies listed on the Nasdaq exchange.",
  },
}

export function getAssetDisplayName(ticker: string): string {
  return ASSETS[ticker]?.label ?? ticker
}

export function getAssetShortName(ticker: string): string {
  return ASSETS[ticker]?.short ?? ticker
}

export function getAssetHelp(ticker: string): string | undefined {
  return ASSETS[ticker]?.help
}

// --- portfolio strategies ---------------------------------------------------

const STRATEGIES: Record<string, TermInfo> = {
  risk_conditioned: {
    label: "Risk-Based Strategy",
    technical: "Risk-conditioned strategy selection (default)",
    help: "Lets WealthPilot choose the portfolio method that its rules assign to your risk profile.",
  },
  mvo: {
    label: "Optimized Portfolio",
    technical: "Mean–Variance Optimization (MVO)",
    help: "Chooses the mix by weighing expected return against how much returns may vary.",
  },
  hrp: {
    label: "Risk-Balanced Portfolio",
    technical: "Hierarchical Risk Parity (HRP)",
    help: "Spreads risk so that no single group of similar investments dominates.",
  },
  equal_weight: {
    label: "Equal Allocation",
    technical: "1/N Equal-Weight Allocation",
    help: "Splits the money equally between the available investments.",
  },
}
STRATEGIES["1/N"] = STRATEGIES.equal_weight

export function getStrategyInfo(value: string | null | undefined): TermInfo | null {
  if (!value) return null
  return STRATEGIES[value] ?? { label: value, technical: value, help: "" }
}

export function getStrategyDisplayName(value: string | null | undefined): string | null {
  return getStrategyInfo(value)?.label ?? null
}

// --- customer type -----------------------------------------------------

/** FAR-Trans's own closed `customerType` vocabulary (verified against
 * `datasets/raw/FAR-Trans/customer_information.csv`: exactly these five
 * values occur) -- a banking-tier label, not a technical code, so only
 * "Mass" (industry jargon for the general-public tier) gets a plainer
 * word; the others are already ordinary English. */
const CUSTOMER_TYPES: Record<string, string> = {
  Mass: "Standard",
  Premium: "Premium",
  Professional: "Professional",
  "Legal Entity": "Business / organization",
  Inactive: "Inactive",
}

export function getCustomerTypeDisplayName(value: string | null | undefined): string | null {
  if (!value) return null
  return CUSTOMER_TYPES[value] ?? value
}

// --- market regime -----------------------------------------------------

/** The market model's own closed regime vocabulary (`training/market/
 * regime.py::classify_regimes`) -- already ordinary words, so this only
 * adds one short clause per value for a reader unfamiliar with the term. */
const MARKET_REGIME_HELP: Record<string, string> = {
  Volatile: "prices have been moving up and down more than usual",
  Trending: "prices have been moving steadily in one direction",
  "Range-bound": "prices have been moving sideways, within a narrow range",
}

export function getMarketRegimeExplanation(value: string | null | undefined): string | undefined {
  return value ? MARKET_REGIME_HELP[value] : undefined
}

// --- investment-capacity bands ---------------------------------------------

/** FAR-Trans capacity categories. The dataset's own thresholds are in euros
 * (`lib/format.ts` documents this); the label below only relabels them with
 * the ₹ display symbol `lib/format.ts` now uses, for the same presentation
 * reason -- the band's numeric threshold (30/80/300) is unchanged. A
 * capacity band is a classification -- never present it as current wealth. */
const CAPACITY_BANDS: Record<string, string> = {
  CAP_LT30K: "Below ₹30K",
  CAP_30K_80K: "₹30K–₹80K",
  CAP_80K_300K: "₹80K–₹300K",
  CAP_GT300K: "Above ₹300K",
}

export const CAPACITY_OPTIONS = Object.entries(CAPACITY_BANDS).map(([value, label]) => ({ value, label }))

export function getCapacityDisplayName(code: string | null | undefined): string | null {
  if (!code) return null
  return CAPACITY_BANDS[code] ?? code
}

// --- portfolio metrics ------------------------------------------------------

export const METRICS = {
  expectedReturn: {
    label: "Expected return",
    technical: "Expected return",
    help: "An estimate based on the model's historical inputs and assumptions. It is not a guarantee.",
  },
  expectedVariability: {
    label: "Expected variability",
    technical: "Volatility",
    help: "An estimate of how much returns may go up and down. Higher variability means returns can move more widely.",
  },
  riskAdjusted: {
    label: "Risk-adjusted performance",
    technical: "Sharpe ratio",
    help: "A technical measure that compares expected return with the amount of variability involved.",
  },
} satisfies Record<string, TermInfo>

// --- plain-language recommendation reasons ----------------------------------

/**
 * Turns the recommendation's own structured rationale fields (never its raw
 * `reasons[]` strings, which are written for a technical reader) into a
 * short list of plain sentences for the primary UI. Every clause is
 * conditioned on a real backend field (a category, a label, or an alignment
 * boolean already computed by `agents/recommendation.py`) -- nothing here
 * invents a new judgement, weighs a number, or states a reason the backend
 * did not already report. An input with no fields returns an empty list.
 */
export function getPlainRecommendationReasons(input: {
  riskCategory?: string | null
  riskBasedStrategy?: string | null
  goalFeasibilityUsed?: string | null
  goalPreferenceAligned?: boolean | null
  marketRegimeUsed?: string | null
  marketPreferenceAligned?: boolean | null
}): string[] {
  const reasons: string[] = []

  if (input.riskBasedStrategy) {
    const strategyLabel = getStrategyDisplayName(input.riskBasedStrategy)
    reasons.push(
      input.riskCategory
        ? `Your risk profile (${input.riskCategory}) points toward ${strategyLabel}.`
        : `Your risk profile points toward ${strategyLabel}.`,
    )
  }

  if (input.goalFeasibilityUsed) {
    reasons.push(
      input.goalPreferenceAligned === false
        ? `Some of your goals need attention right now (${input.goalFeasibilityUsed}), so the plan adjusts for that while staying within your comfort level.`
        : `Your goals currently look ${input.goalFeasibilityUsed.toLowerCase()}, so the plan can follow your risk-based strategy.`,
    )
  }

  if (input.marketRegimeUsed) {
    reasons.push(
      input.marketPreferenceAligned === false
        ? `Markets are currently ${input.marketRegimeUsed.toLowerCase()}, but your personal risk profile remains the stronger factor in choosing your plan.`
        : `Current market conditions (${input.marketRegimeUsed}) support this approach.`,
    )
  }

  return reasons
}

// --- help text for other recurring terms -----------------------------------

export const HELP = {
  riskProfile: "How much ups and downs in investment value your profile suggests you can accept, as classified by the risk assessment.",
  capacityBand: "An investment-capacity category recorded for this profile. It is a classification band, not a measure of your current wealth.",
  customerType: "The customer category recorded for this profile in the source data.",
  investmentAllocation: "How the money in the proposed plan is split between different investments.",
  emergencySavings: "Money set aside to help cover essential expenses during unexpected situations.",
  complianceCheck: "A set of safety rules every plan must pass. If a rule is not met, WealthPilot stops the plan instead of proposing it.",
  portfolioStrategy: "The method used to decide how the money is split between investments.",
  riskConfidence: "How strongly the risk assessment favours this category over the others. It is not a percentage of your money.",
  inflationAdjusted: "The target expressed in future money, after allowing for expected price rises (inflation).",
  requiredContribution: "The amount the calculation says you would need to put aside at each contribution (for example, each month) to reach the target.",
  contributionGap: "The difference between the required contribution and the contribution you plan to make. A negative number means your plan is ahead.",
  goalChance: "How often the goal was reached across many simulated market scenarios. It is an estimate, not a promise.",
  marketCondition: "The recent pattern of price movements for this market, as labelled by the market model.",
} as const

// --- risk categories --------------------------------------------------------

const RISK_CATEGORY_HELP: Record<string, string> = {
  Aggressive: "More comfortable with larger ups and downs in pursuit of higher long-term growth.",
  Balanced: "Seeks a balance between growth and stability.",
  Conservative: "Places more emphasis on stability and lower variability.",
  Income: "Places greater emphasis on generating regular income.",
}

export function getRiskCategoryDescription(category: string | null | undefined): string | undefined {
  return category ? RISK_CATEGORY_HELP[category] : undefined
}

// --- statuses (StatusBadge) -------------------------------------------------

/** Plain labels for every status vocabulary the API returns. The raw value
 * is never altered -- only the words shown for it. A rejected or blocked
 * status is never worded so that it could read as an approval. */
const STATUS_LABELS: Record<string, string> = {
  // compliance decision
  PASS: "Passed",
  WARN: "Passed with warnings",
  REJECT: "Not approved",
  // recommendation status
  approved: "Approved",
  savings_first: "Savings first",
  blocked_rejected: "Blocked by compliance",
  // overall analysis status
  rejected: "Not approved",
  pending_information: "More information needed",
  failed: "Could not complete",
  // emergency fund
  sufficient: "Sufficient",
  insufficient: "Below target",
  // goal feasibility keeps the backend's own words
  Feasible: "Feasible",
  "At Risk": "At Risk",
  "Not Feasible": "Not Feasible",
}

export function getStatusLabel(status: string): string | undefined {
  return STATUS_LABELS[status]
}

const FEASIBILITY_HELP: Record<string, string> = {
  Feasible: "Your current financial information supports this goal.",
  "At Risk": "This goal may require changes to your current plan.",
  "Not Feasible": "Your current financial information does not currently support this goal.",
}

export function getFeasibilityExplanation(feasibility: string | null | undefined): string | undefined {
  return feasibility ? FEASIBILITY_HELP[feasibility] : undefined
}

// --- compliance rules -------------------------------------------------------

/** Plain names for the rules in `config/compliance_rules.yaml`, keyed by the
 * rule's own id. An unknown id falls back to the backend's description. No
 * threshold is restated here, so nothing can drift from the rule file. */
const COMPLIANCE_RULE_NAMES: Record<string, string> = {
  weights_sum_to_one: "The whole amount is allocated — the shares add up to 100%.",
  no_negative_weights: "No short selling — no investment has a negative share.",
  qqq_within_risk_band: "The share in Nasdaq-100 / US Growth stays within the range allowed for this risk profile.",
  single_asset_cap: "No single investment takes more than the allowed maximum share.",
  emergency_fund_savings_first: "If emergency savings are below target, savings come first — no normal investment plan is proposed.",
}

export function getComplianceRuleName(ruleId: string, fallback: string): string {
  return COMPLIANCE_RULE_NAMES[ruleId] ?? fallback
}

// --- analysis steps (Agent Activity) ----------------------------------------

interface StepInfo {
  label: string
  /** Where the step runs, for the technical-details table. */
  framework: string
}

const GRAPH = "LangGraph node"
const ANALYSIS_STEPS: Record<string, StepInfo> = {
  analysis_started: { label: "Analysis started", framework: "Stream start event" },
  customer_analyzer: { label: "Checking your profile", framework: GRAPH },
  risk_analyst: { label: "Assessing risk", framework: GRAPH },
  information_request: { label: "Requesting more information", framework: GRAPH },
  financial_health_analyst: { label: "Reviewing financial information", framework: GRAPH },
  reprofile: { label: "Re-checking risk after a behaviour change", framework: GRAPH },
  goal_analyst: { label: "Checking goals", framework: GRAPH },
  market_analyst: { label: "Reviewing market conditions", framework: GRAPH },
  portfolio_manager: { label: "Evaluating portfolio options", framework: GRAPH },
  savings_first: { label: "Prioritising emergency savings", framework: GRAPH },
  compliance_analyst: { label: "Running compliance checks", framework: GRAPH },
  approved: { label: "Analysis outcome", framework: GRAPH },
  rejected: { label: "Analysis outcome", framework: GRAPH },
  pending_information: { label: "Analysis outcome", framework: GRAPH },
  failed: { label: "Analysis outcome", framework: GRAPH },
  recommendation: { label: "Preparing your recommendation", framework: "Recommendation engine (after the graph)" },
  explanation: { label: "Preparing your explanation", framework: "Explanation step (after the graph)" },
  analysis_completed: { label: "Analysis complete", framework: "Stream end event" },
}

export function getAnalysisStep(node: string): StepInfo {
  return ANALYSIS_STEPS[node] ?? { label: node, framework: "Pipeline step" }
}
