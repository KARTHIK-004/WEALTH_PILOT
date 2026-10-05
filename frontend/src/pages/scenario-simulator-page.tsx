import { useState } from "react"

import { ScenarioComparisonChart } from "@/components/charts/scenario-comparison-chart"
import { ErrorState } from "@/components/shell/error-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { TermLabel } from "@/components/shell/help-tip"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useScenarioCompare } from "@/hooks/use-scenario-compare"
import { formatPercent } from "@/lib/format"
import { HELP, METRICS, getStrategyDisplayName, getStrategyInfo } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

type StrategyChoice = "default" | "mvo" | "hrp" | "equal_weight"

/** Plain labels from `lib/terminology.ts`; the `value`s -- what the API
 * receives -- are unchanged ("default" sends no override). Passed to the
 * Select as `items` so the closed trigger shows the label, not the value. */
const STRATEGY_OPTIONS: { value: StrategyChoice; label: string }[] = [
  { value: "default", label: `${getStrategyDisplayName("risk_conditioned")} (default)` },
  { value: "mvo", label: getStrategyDisplayName("mvo") as string },
  { value: "hrp", label: getStrategyDisplayName("hrp") as string },
  { value: "equal_weight", label: getStrategyDisplayName("equal_weight") as string },
]

const STRATEGY_KEYS = ["risk_conditioned", "mvo", "hrp", "equal_weight"] as const

/**
 * Calls `POST /api/scenarios/compare` for the CURRENT customer (section
 * 38 — the established context, never a different/hard-coded customer)
 * with two `portfolio_strategy` overrides. No scenario result, ranking,
 * or "best scenario" score is computed in React (sections 30/32) — the
 * comparison table below only ever displays the two `ScenarioSummary`
 * objects the API returns, side by side, unmodified.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): strategies are
 * offered as Risk-Based Strategy / Optimized Portfolio / Risk-Balanced
 * Portfolio / Equal Allocation, with the real methods (MVO, HRP, 1/N)
 * explained under "How are these strategies calculated?".
 */
export function ScenarioSimulatorPage() {
  const { profileId } = useCustomer()
  const [strategyA, setStrategyA] = useState<StrategyChoice>("default")
  const [strategyB, setStrategyB] = useState<StrategyChoice>("mvo")
  const mutation = useScenarioCompare()

  if (profileId === null) {
    return (
      <PageContainer title="Scenario Simulator" description="Compare two ways of building a portfolio for the same profile, side by side.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    mutation.mutate({
      scenario_a: { profile_id: profileId, portfolio_strategy: strategyA === "default" ? undefined : strategyA },
      scenario_b: { profile_id: profileId, portfolio_strategy: strategyB === "default" ? undefined : strategyB },
    })
  }

  const result = mutation.data

  return (
    <PageContainer title="Scenario Simulator" description="Compare two ways of building a portfolio for the same profile, side by side.">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Choose scenarios</CardTitle>
            <CardDescription>
              Both scenarios use the same profile, goals and market information — only the way the portfolio is
              built differs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="scenario-a-strategy">Scenario A: portfolio strategy</Label>
                <Select items={STRATEGY_OPTIONS} value={strategyA} onValueChange={(value) => setStrategyA(value as StrategyChoice)}>
                  <SelectTrigger id="scenario-a-strategy" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STRATEGY_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="scenario-b-strategy">Scenario B: portfolio strategy</Label>
                <Select items={STRATEGY_OPTIONS} value={strategyB} onValueChange={(value) => setStrategyB(value as StrategyChoice)}>
                  <SelectTrigger id="scenario-b-strategy" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STRATEGY_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="sm:col-span-2">
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? "Comparing…" : "Compare scenarios"}
                </Button>
              </div>
              <TechnicalDetails className="sm:col-span-2" title="How are these strategies calculated?">
                <dl className="space-y-2">
                  {STRATEGY_KEYS.map((key) => {
                    const info = getStrategyInfo(key)
                    return info ? (
                      <div key={key}>
                        <dt className="font-medium">{info.label}</dt>
                        <dd className="text-muted-foreground">
                          {info.technical}. {info.help}
                        </dd>
                      </div>
                    ) : null
                  })}
                </dl>
              </TechnicalDetails>
            </form>
          </CardContent>
        </Card>

        {mutation.isError ? <ErrorState error={mutation.error} onRetry={() => mutation.reset()} /> : null}

        {result ? (
          <Card>
            <CardHeader>
              <CardTitle>Return and variability comparison</CardTitle>
              <CardDescription>
                The estimated figures for both scenarios, side by side. This is a comparison only — neither
                scenario is ranked or recommended over the other.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScenarioComparisonChart scenarioA={result.scenario_a} scenarioB={result.scenario_b} />
            </CardContent>
          </Card>
        ) : null}

        {result ? (
          <Card>
            <CardHeader>
              <CardTitle>Comparison</CardTitle>
              <CardDescription>The results calculated for each scenario.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Result</TableHead>
                    <TableHead>Scenario A</TableHead>
                    <TableHead>Scenario B</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="text-muted-foreground">
                      <TermLabel help={HELP.riskProfile}>Risk profile</TermLabel>
                    </TableCell>
                    <TableCell>{result.scenario_a.risk_category ?? "Not available"}</TableCell>
                    <TableCell>{result.scenario_b.risk_category ?? "Not available"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="text-muted-foreground">
                      <TermLabel help={HELP.portfolioStrategy}>Portfolio strategy</TermLabel>
                    </TableCell>
                    <TableCell>{getStrategyDisplayName(result.scenario_a.portfolio_strategy) ?? "Not available"}</TableCell>
                    <TableCell>{getStrategyDisplayName(result.scenario_b.portfolio_strategy) ?? "Not available"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="text-muted-foreground">
                      <TermLabel help={METRICS.expectedReturn.help}>{METRICS.expectedReturn.label}</TermLabel>
                    </TableCell>
                    <TableCell>{formatPercent(result.scenario_a.expected_return)}</TableCell>
                    <TableCell>{formatPercent(result.scenario_b.expected_return)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="text-muted-foreground">
                      <TermLabel help={METRICS.expectedVariability.help}>{METRICS.expectedVariability.label}</TermLabel>
                    </TableCell>
                    <TableCell>{formatPercent(result.scenario_a.expected_volatility)}</TableCell>
                    <TableCell>{formatPercent(result.scenario_b.expected_volatility)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="text-muted-foreground">
                      <TermLabel help={METRICS.riskAdjusted.help}>{METRICS.riskAdjusted.label}</TermLabel>
                    </TableCell>
                    <TableCell>{result.scenario_a.sharpe_ratio?.toFixed(2) ?? "Not available"}</TableCell>
                    <TableCell>{result.scenario_b.sharpe_ratio?.toFixed(2) ?? "Not available"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="text-muted-foreground">
                      <TermLabel help={HELP.complianceCheck}>Compliance check</TermLabel>
                    </TableCell>
                    <TableCell><StatusBadge status={result.scenario_a.compliance_decision} /></TableCell>
                    <TableCell><StatusBadge status={result.scenario_b.compliance_decision} /></TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="text-muted-foreground">Recommendation status</TableCell>
                    <TableCell><StatusBadge status={result.scenario_a.recommendation_status} /></TableCell>
                    <TableCell><StatusBadge status={result.scenario_b.recommendation_status} /></TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="text-muted-foreground">Goal outlook</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {result.scenario_a.goal_feasibility.length
                          ? result.scenario_a.goal_feasibility.map((f, i) => <StatusBadge key={i} status={f} />)
                          : "None"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {result.scenario_b.goal_feasibility.length
                          ? result.scenario_b.goal_feasibility.map((f, i) => <StatusBadge key={i} status={f} />)
                          : "None"}
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              <TechnicalDetails
                className="mt-4"
                items={[
                  { label: "Scenario A strategy (API value)", value: result.scenario_a.portfolio_strategy },
                  { label: "Scenario B strategy (API value)", value: result.scenario_b.portfolio_strategy },
                  { label: "Scenario A method", value: getStrategyInfo(result.scenario_a.portfolio_strategy)?.technical },
                  { label: "Scenario B method", value: getStrategyInfo(result.scenario_b.portfolio_strategy)?.technical },
                  { label: "Volatility (A / B)", value: `${formatPercent(result.scenario_a.expected_volatility, 1)} / ${formatPercent(result.scenario_b.expected_volatility, 1)}` },
                  { label: "Sharpe ratio (A / B)", value: `${result.scenario_a.sharpe_ratio?.toFixed(2) ?? "not available"} / ${result.scenario_b.sharpe_ratio?.toFixed(2) ?? "not available"}` },
                  { label: "Compliance decision (A / B)", value: `${result.scenario_a.compliance_decision ?? "not available"} / ${result.scenario_b.compliance_decision ?? "not available"}` },
                ]}
              />
            </CardContent>
          </Card>
        ) : null}
      </div>
    </PageContainer>
  )
}
