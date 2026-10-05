import { Activity, BookOpen, CircleAlert, Gauge, ListChecks, PiggyBank, Scale, Target, TrendingUp } from "lucide-react"

import { RationaleInPlainWords } from "@/components/portfolio/rationale-in-plain-words"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatCurrency, formatDate, formatPercent } from "@/lib/format"
import {
  getAssetDisplayName,
  getComplianceRuleName,
  getRiskCategoryDescription,
  getStrategyInfo,
} from "@/lib/terminology"
import type { components } from "@/types/api"

type Analysis = components["schemas"]["AnalysisResult"]
type ProfileGoal = components["schemas"]["GoalOut"]

/**
 * The "Simple" view of Why This Recommendation — the analysis explained for a
 * reader with no financial background.
 *
 * **Presentation only.** Every figure is a value the analysis API already
 * returned, shown through the existing `formatCurrency` / `formatPercent`
 * formatters. The sentences are fixed wording chosen by the backend's own
 * statuses and flags (the overall `status`, `recommendation.status`,
 * `emergency_fund.sufficient`, each goal's `feasibility`, the compliance
 * decision). Nothing here calculates, compares or ranks a financial value: no
 * difference, no total, no goal-versus-goal comparison, no score. A shortfall
 * is shown only because the backend computed it.
 *
 * It is built from the deterministic results rather than from new AI text on
 * purpose: every analysis — AI wording included — is stored and served from
 * cache, and the AI service may be unavailable, so this view works for every
 * analysis, including ones computed before it existed. The AI's own wording
 * (or its checked template fallback) is unchanged in the Detailed view.
 *
 * Backend reasons written for developers ("no GoalAssumptions … supplied") are
 * never paraphrased into a claim they do not make: the plain sentence states
 * only what the status shows, and the original reason is kept as a small
 * "technical detail" line.
 *
 * Terminology (`docs/DESIGN.md` section 30): investments, strategies and
 * compliance rules are named in plain words via `lib/terminology.ts`
 * ("Nasdaq-100 / US Growth", "Optimized Portfolio"); the tickers, method
 * names and backend reasons remain in Technical details / the glossary.
 */

type Outcome = "approved" | "savings_first" | "rejected" | "pending" | "failed"

function outcomeOf(data: Analysis): Outcome {
  if (data.status === "pending_information") return "pending"
  if (data.status === "rejected") return "rejected"
  if (data.status === "failed") return "failed"
  return data.recommendation?.status === "savings_first" ? "savings_first" : "approved"
}

const HEADLINE: Record<Outcome, { title: string; text: string }> = {
  approved: {
    title: "Analysis complete — plan proposed",
    text: "WealthPilot has finished analysing your information. It proposes an investment plan, and that plan passed all of its safety (compliance) checks.",
  },
  savings_first: {
    title: "Analysis complete — savings first",
    text: "WealthPilot has finished analysing your information. Before any investing, it recommends building up your emergency savings first.",
  },
  rejected: {
    title: "Plan stopped by a safety check",
    text: "WealthPilot's safety (compliance) checks stopped an investment plan for this profile, so no plan is proposed.",
  },
  pending: {
    title: "More information needed",
    text: "WealthPilot needs more information before it can complete your analysis.",
  },
  failed: {
    title: "Analysis could not be completed",
    text: "The analysis could not be completed this time. Please try again later.",
  },
}

const GLOSSARY: Record<string, string> = {
  "Risk profile":
    "How much ups and downs in investment value your situation suggests you can accept. WealthPilot groups profiles as Conservative, Income, Balanced or Aggressive.",
  "Emergency fund":
    "Money set aside for unexpected costs, such as losing income or an urgent repair, that you can reach quickly.",
  "Compliance check":
    "A safety rule the plan must pass. If a rule is not met, WealthPilot stops the plan rather than proposing something unsuitable.",
  "Savings first":
    "WealthPilot's rule that building emergency savings comes before investing when those savings are not yet enough.",
  "Monte Carlo simulation":
    "A method that tests many possible futures, using past market behaviour, to estimate how often a goal is reached.",
  Feasibility:
    "WealthPilot's label for a goal's calculated probability: Feasible, At Risk or Not Feasible.",
  Diversification: "Spreading money across different investments rather than depending on only one.",
  "Optimized Portfolio":
    "A way of choosing how to split money between investments by weighing expected return against how much returns may vary. Technical name: Mean–Variance Optimization (MVO).",
  "Risk-Balanced Portfolio":
    "A way of splitting money so that no single group of similar investments dominates the risk. Technical name: Hierarchical Risk Parity (HRP).",
  "Equal Allocation": "Splitting money equally between the available investments. Technical name: 1/N equal-weight allocation.",
  "Expected variability": "An estimate of how much returns may go up and down. Technical name: volatility.",
  "Risk-adjusted performance":
    "A technical measure that compares expected return with the amount of variability involved. Technical name: Sharpe ratio.",
}

/** Holdings whose weight displays above 0% — a formatting check, not a calculation. */
function shownHoldings(weights: Record<string, number> | null | undefined): [string, number][] {
  return Object.entries(weights ?? {}).filter(([, weight]) => formatPercent(weight, 0) !== "0%")
}

function joinPlain(parts: string[]): string {
  if (parts.length <= 1) return parts.join("")
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  )
}

function TechnicalDetail({ text }: { text: string | null | undefined }) {
  if (!text) return null
  return <p className="text-muted-foreground text-xs">Technical detail: {text}</p>
}

function Section({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Target
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="text-muted-foreground size-4" /> {title}
        </CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm leading-relaxed">{children}</CardContent>
    </Card>
  )
}

export function PlainLanguageExplanation({
  data,
  profileGoals,
}: {
  data: Analysis
  profileGoals: ProfileGoal[] | undefined
}) {
  const outcome = outcomeOf(data)
  const ef = data.emergency_fund
  const efKnown = ef !== null && ef.current_amount !== null && ef.required_amount !== null
  const rec = data.recommendation
  const holdings = rec?.status === "approved" ? shownHoldings(rec.weights) : []
  const triggered = (data.compliance?.rule_results ?? []).filter((rule) => rule.triggered)
  const goalDate = (goalId: number) => profileGoals?.find((goal) => goal.id === goalId)?.target_date
  const anyProbability = data.goals.some((goal) => goal.monte_carlo_success_probability !== null)
  const goalsMissingInputs = data.goals.some((goal) => goal.monte_carlo_success_probability === null)

  // --- why this result: the factors actually present in this analysis
  const factors: string[] = []
  if (data.risk?.risk_category) factors.push("your risk profile, from the risk assessment model")
  if (data.financial_health?.behaviour_drift_flag !== null && data.financial_health?.behaviour_drift_flag !== undefined)
    factors.push("patterns in your past investment behaviour")
  if (efKnown) factors.push("your emergency-fund position")
  if (data.goals.length > 0) factors.push("your goals")
  if (data.market?.instruments.length) factors.push("recent market conditions for each investment")
  if (rec?.status === "approved" && rec.weights) factors.push("an analysis of possible portfolios")
  if (data.compliance) factors.push("WealthPilot's safety (compliance) rules")

  // --- important points: one statement per backend status, never a comparison
  const points: string[] = []
  if (data.compliance?.decision === "PASS") points.push("The plan passed WealthPilot's compliance (safety) check.")
  if (data.compliance?.decision === "WARN") points.push("The plan passed WealthPilot's compliance (safety) check, with a warning.")
  if (data.compliance?.decision === "REJECT") points.push("The plan did not pass WealthPilot's compliance (safety) check, so no plan is proposed.")
  if (rec?.status === "approved") points.push("Your risk profile takes priority over goal and market preferences when the approach is chosen.")
  if (efKnown && ef?.sufficient === true) points.push("Your available savings cover the emergency-fund amount WealthPilot calculated.")
  if (efKnown && ef?.sufficient === false) points.push("Your available savings are below the emergency-fund amount WealthPilot calculated.")
  if (!efKnown && ef?.unavailable_reason && outcome !== "pending") points.push("Your emergency fund could not be checked, because the information it needs has not been provided.")
  for (const goal of data.goals) {
    if (goal.feasibility === "At Risk" || goal.feasibility === "Not Feasible")
      points.push(`Your “${goal.goal_type}” goal is currently labelled ${goal.feasibility}.`)
  }
  for (const rule of triggered) {
    if (rule.severity === "WARN") points.push(`Compliance warning: ${rule.message}`)
  }
  if (outcome === "savings_first") points.push("No investment plan is proposed until your emergency savings reach the calculated amount.")
  if (outcome === "pending") points.push("Some required information is missing, so parts of the analysis could not run.")
  points.push("These results rely on the information you provided and on past market data. They can change when your situation changes.")

  // --- next steps: neutral and practical; no new strategy, no buy/sell
  const steps: string[] = []
  if (outcome === "pending") steps.push("Complete the missing profile information so WealthPilot can finish the analysis.")
  if (!efKnown && ef?.unavailable_reason && outcome !== "pending")
    steps.push("Add your essential monthly expenses and available savings under Customer Profile → Your financial information.")
  if (goalsMissingInputs && outcome !== "pending")
    steps.push("Add your goal planning assumptions (monthly contribution, expected return and inflation) under Customer Profile → Your financial information.")
  if (outcome === "savings_first") steps.push("Keep building your emergency savings toward the calculated amount.")
  steps.push("Update your financial information when your income or expenses change.")
  steps.push("Review your goals if your plans or dates change, and look at this plan again from time to time.")

  // --- glossary: only the terms this analysis actually involves
  const terms: string[] = []
  if (data.risk?.risk_category) terms.push("Risk profile")
  if (efKnown || ef?.unavailable_reason) terms.push("Emergency fund")
  if (data.compliance) terms.push("Compliance check")
  if (outcome === "savings_first" || triggered.some((rule) => rule.rule_id === "emergency_fund_savings_first")) terms.push("Savings first")
  if (anyProbability) terms.push("Monte Carlo simulation", "Feasibility")
  if (holdings.length > 1) terms.push("Diversification")
  const strategyInfo = getStrategyInfo(rec?.selected_strategy)
  if (rec?.status === "approved" && strategyInfo && GLOSSARY[strategyInfo.label]) terms.push(strategyInfo.label)
  if (rec?.status === "approved" && rec.expected_volatility !== null) terms.push("Expected variability")
  if (rec?.status === "approved" && rec.sharpe_ratio !== null) terms.push("Risk-adjusted performance")

  const headline = HEADLINE[outcome]

  return (
    <div className="space-y-4">
      <Section icon={Scale} title="Your financial summary">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={outcome === "approved" ? "default" : "secondary"}>{headline.title}</Badge>
          {data.risk?.risk_category ? <Badge variant="outline">Risk profile: {data.risk.risk_category}</Badge> : null}
        </div>
        <p>{headline.text}</p>
        {data.risk?.risk_category ? null : outcome === "pending" ? (
          <>
            <p>WealthPilot could not assess your risk profile yet, so the rest of the analysis could not run.</p>
            <TechnicalDetail text={data.risk?.unavailable_reason} />
          </>
        ) : null}
      </Section>

      {data.risk?.risk_category ? (
        <Section icon={Gauge} title="Your risk profile">
          <p>
            Your risk profile was assessed as <span className="font-medium">{data.risk.risk_category}</span> by the
            risk assessment model. {getRiskCategoryDescription(data.risk.risk_category) ?? ""}
          </p>
        </Section>
      ) : null}

      {data.financial_health && Object.keys(data.financial_health).length > 0 ? (
        <Section icon={Activity} title="Your financial health">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              {data.financial_health.expense_persona
                ? `Spending pattern: ${data.financial_health.expense_persona}.`
                : "Spending-pattern insights are unavailable: the spending-pattern model was built from a separate dataset and, by design, is not applied to this profile. No pattern is assumed."}
            </li>
            {data.financial_health.behaviour_drift_flag !== null && data.financial_health.behaviour_drift_flag !== undefined ? (
              <li>
                {data.financial_health.behaviour_drift_flag
                  ? "A significant change in your financial behaviour was detected."
                  : "No significant change in your financial behaviour was detected."}
              </li>
            ) : null}
            {data.financial_health.isolation_forest_anomaly !== null && data.financial_health.isolation_forest_anomaly !== undefined ? (
              <li>
                {data.financial_health.isolation_forest_anomaly ? "Unusual activity was detected." : "No unusual activity was detected."}
              </li>
            ) : null}
          </ul>
        </Section>
      ) : null}

      {/* Only when there is something to show: figures, or a backend reason they are
          missing. A pipeline that stopped earlier (e.g. pending information) never
          evaluated the emergency fund, and this view does not claim otherwise. */}
      {ef && (efKnown || ef.unavailable_reason) ? (
        <Section icon={PiggyBank} title="Your emergency savings">
          {efKnown ? (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <Figure label="Available now" value={formatCurrency(ef.current_amount)} />
                <Figure label="Calculated requirement" value={formatCurrency(ef.required_amount)} />
                <Figure label="Shortfall" value={ef.shortfall === null ? "Not provided" : formatCurrency(ef.shortfall)} />
              </div>
              <p>
                {ef.sufficient
                  ? "Your available savings cover the emergency-fund amount WealthPilot calculated from your essential expenses."
                  : "Your available savings are below the emergency-fund amount WealthPilot calculated from your essential expenses. The shortfall is the gap WealthPilot calculated."}
              </p>
            </>
          ) : (
            <>
              <p>
                WealthPilot could not check your emergency fund, because the information it needs — your essential
                monthly expenses and the savings you have available — has not been provided.
              </p>
              <TechnicalDetail text={ef.unavailable_reason} />
            </>
          )}
        </Section>
      ) : null}

      <Section icon={Target} title="Your goals">
        {data.goals.length === 0 ? (
          <p className="text-muted-foreground">
            {profileGoals && profileGoals.length > 0
              ? "Your goals are recorded but have not been evaluated yet, because the analysis did not reach that step."
              : "No goals have been recorded."}
          </p>
        ) : (
          <div className="space-y-4">
            {data.goals.map((goal) => {
              const date = goalDate(goal.goal_id)
              return (
                <div key={goal.goal_id} className="space-y-2 rounded-lg border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{goal.goal_type}</p>
                    {goal.feasibility ? <StatusBadge status={goal.feasibility} /> : null}
                  </div>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <Figure label="Target" value={formatCurrency(goal.nominal_target_amount)} />
                    {date ? <Figure label="Target date" value={formatDate(date)} /> : null}
                    <Figure
                      label="Calculated probability"
                      value={goal.monte_carlo_success_probability === null ? "Not calculated" : formatPercent(goal.monte_carlo_success_probability, 1)}
                    />
                  </div>
                  {goal.monte_carlo_success_probability !== null ? (
                    <p>
                      The calculated probability is {formatPercent(goal.monte_carlo_success_probability, 1)}. WealthPilot
                      tested many possible futures under your current assumptions; this is how often the goal was
                      reached. It is an estimate, not a promise.
                    </p>
                  ) : (
                    <>
                      <p>The chance of reaching this goal could not be calculated with the information available.</p>
                      <TechnicalDetail text={goal.unavailable_reason} />
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Section>

      <Section icon={TrendingUp} title="Your investment allocation">
        {rec?.status === "approved" && rec.weights ? (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Investment</TableHead>
                    <TableHead className="text-right">Share of the plan</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(rec.weights).map(([ticker, weight]) => (
                    <TableRow key={ticker}>
                      <TableCell className="font-medium whitespace-normal">{getAssetDisplayName(ticker)}</TableCell>
                      <TableCell className="text-right">{formatPercent(weight, 0)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {holdings.length > 0 ? (
              <p>
                {`The proposed portfolio places ${joinPlain(holdings.map(([ticker, weight]) => `${formatPercent(weight, 0)} in ${getAssetDisplayName(ticker)}`))}.`}
                {holdings.length > 1
                  ? " Spreading the money this way means the plan does not depend entirely on a single investment."
                  : ""}
              </p>
            ) : null}
            {strategyInfo ? (
              <p>
                The split was chosen using the {strategyInfo.label} approach, based on past market data. It is a
                proposal, not a guarantee of future returns.
              </p>
            ) : null}
            <TechnicalDetails
              items={[
                { label: "Method", value: strategyInfo?.technical },
                { label: "Tickers", value: Object.keys(rec.weights).join(", ") },
              ]}
            />
          </>
        ) : (
          <p>
            {outcome === "savings_first"
              ? "No investment plan is proposed yet. WealthPilot recommends building your emergency savings first."
              : outcome === "rejected"
                ? "No investment plan was produced, because the safety (compliance) checks stopped it."
                : "No investment plan is available until the analysis is complete."}
          </p>
        )}
      </Section>

      <Section
        icon={ListChecks}
        title="Why this result makes sense"
        description="The calculations and decisions were made by WealthPilot's own models and rules. The AI (Gemini) only writes the wording that explains them; it does not calculate or decide anything."
      >
        {factors.length > 0 ? (
          <>
            <p>WealthPilot considered:</p>
            <ul className="list-disc space-y-1 pl-5">
              {factors.map((factor) => (
                <li key={factor}>{factor}</li>
              ))}
            </ul>
          </>
        ) : (
          <p>The analysis stopped before WealthPilot could consider your information.</p>
        )}
        {rec?.status === "approved" ? <RationaleInPlainWords recommendation={rec} /> : null}
        {triggered.filter((rule) => rule.severity === "REJECT").map((rule) => (
          <p key={rule.rule_id}>
            <span className="font-medium">The safety rule that stopped the plan:</span>{" "}
            {getComplianceRuleName(rule.rule_id, rule.description)} {rule.message}
          </p>
        ))}
      </Section>

      <Section icon={CircleAlert} title="Important constraints">
        <ul className="list-disc space-y-1 pl-5">
          {points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </Section>

      <Section icon={ListChecks} title="Next steps">
        <ul className="list-disc space-y-1 pl-5">
          {steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      </Section>

      {terms.length > 0 ? (
        <Section icon={BookOpen} title="Words explained">
          <dl className="space-y-2">
            {terms.map((term) => (
              <div key={term}>
                <dt className="font-medium">{term}</dt>
                <dd className="text-muted-foreground">{GLOSSARY[term]}</dd>
              </div>
            ))}
          </dl>
        </Section>
      ) : null}
    </div>
  )
}
