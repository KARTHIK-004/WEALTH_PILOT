import { FlaskConical } from "lucide-react"
import { Link } from "react-router"

import { MonthlyFlowsChart } from "@/components/charts/monthly-flows-chart"
import { BehaviourOverviewView, InvestmentBehaviourView, SpendingPatternView } from "@/components/financial-health/behaviour-sections"
import { BehaviourSentimentView, type BehaviourSentimentViewProps } from "@/components/financial-health/behaviour-sentiment-view"
import { DemoErrorState, DemoExamples, type DemoExample } from "@/components/financial-health/demo-financial-behaviour"
import { HouseholdFinancialSummaryView } from "@/components/profile/household-financial-summary"
import { LoadingState } from "@/components/shell/loading-state"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { monthLabel } from "@/lib/behaviour-overview"
import { DEMO_PAGE_PATH } from "@/lib/demo-mode"
import { formatCurrency, formatPercent } from "@/lib/format"
import { investmentBehaviour } from "@/lib/investment-behaviour"
import type { SpendingPatternState } from "@/lib/spending-pattern"
import type { components } from "@/types/api"

type Family = components["schemas"]["DemoFamilyFinancialBehaviourResponse"]
type Member = components["schemas"]["DemoMemberOut"]
type Month = components["schemas"]["DemoMonthOut"]
type Feature = components["schemas"]["FeatureValueOut"]

export const FAMILY_BANNER_TITLE = "Demo data — fictional family example"
export const FAMILY_BANNER_FALLBACK =
  "Every name, month, amount and sentence on this page is invented and fixed. It is not a real household's record, nothing is stored, and it does not affect any risk profile, allocation or recommendation."
export const FAMILY_PAGE_DESCRIPTION =
  "A walk-through with a fictional family: each member's reported months and what they show, the household's own totals, and an optional note. This only explains: it changes nothing about a risk profile, an allocation or a recommendation."
export const INDIVIDUAL_COMMITMENTS_TITLE = "Not recorded for an individual"
export const INDIVIDUAL_COMMITMENTS_MESSAGE = "WealthPilot does not record loans or EMIs for an individual, so none are shown and none are assumed."
const DEMO_SPENDING_STATE: SpendingPatternState = { kind: "model_unavailable", pattern: null, reason: "This is fictional demo data, so the spending model is not applied to it." }
const NOT_AVAILABLE = "Not available"
const NOT_PROVIDED = "Not provided"

const money = (value: number | null | undefined): string => (value === null || value === undefined ? NOT_PROVIDED : formatCurrency(value))

function Calculated({ feature, signed = false }: { feature: Feature; signed?: boolean }) {
  if (feature.value === null || feature.value === undefined) {
    return (
      <span title={feature.unavailable_reason ?? undefined}>
        {NOT_AVAILABLE}
        {feature.unavailable_reason ? <span className="sr-only"> ({feature.unavailable_reason})</span> : null}
      </span>
    )
  }
  const text = formatPercent(feature.value, 1)
  return <span>{signed && feature.value > 0 ? `+${text}` : text}</span>
}

export function FamilyDemoBanner({ notice }: { notice?: string }) {
  return (
    <Alert role="status" aria-label="Family demonstration mode is active" className="border-primary/40">
      <FlaskConical aria-hidden="true" />
      <AlertTitle className="flex flex-wrap items-center gap-2">
        {FAMILY_BANNER_TITLE} <Badge variant="outline">Demo</Badge>
      </AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{notice ?? FAMILY_BANNER_FALLBACK}</p>
        <p>
          <Link to={DEMO_PAGE_PATH} className="text-primary underline underline-offset-2">
            Leave demonstration mode
          </Link>
        </p>
      </AlertDescription>
    </Alert>
  )
}

function MemberMonths({ member, index }: { member: Member; index: number }) {
  return (
    <div className="space-y-3">
      <MonthlyFlowsChart points={member.months.map((m: Month) => ({ period: m.period, income: m.income, expenses: m.expenses, savings: m.savings }))} />
      <div className="overflow-x-auto" role="region" aria-label={`${member.label}: monthly records table (scrolls sideways on a narrow screen)`} tabIndex={0}>
        <Table>
          <TableCaption id={`member-${index}-caption`}>
            Fictional monthly records for {member.label} with calculated ratios and changes. A blank amount was not reported; it is not zero.
          </TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Month</TableHead>
              {["Income", "Spending", "Savings", "Investments", "Savings / income", "Income change", "Spending change", "Savings change"].map((name) => (
                <TableHead key={name} scope="col" className="text-right">
                  {name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {member.months.map((m) => (
              <TableRow key={m.period}>
                <TableHead scope="row" className="whitespace-nowrap">
                  {monthLabel(m.period)}
                </TableHead>
                <TableCell className="text-right">{money(m.income)}</TableCell>
                <TableCell className="text-right">{money(m.expenses)}</TableCell>
                <TableCell className="text-right">{money(m.savings)}</TableCell>
                <TableCell className="text-right">{money(m.investment_contribution)}</TableCell>
                <TableCell className="text-right">
                  <Calculated feature={m.savings_to_income} />
                </TableCell>
                <TableCell className="text-right">
                  <Calculated feature={m.income_change.relative_change} signed />
                </TableCell>
                <TableCell className="text-right">
                  <Calculated feature={m.expenses_change.relative_change} signed />
                </TableCell>
                <TableCell className="text-right">
                  <Calculated feature={m.savings_change.relative_change} signed />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

/** One fictional member: the overview, the months (chart and table), investment behaviour, the spending pattern, and the individual loan / EMI wording. Nothing is calculated here. */
export function MemberSection({ member, index }: { member: Member; index: number }) {
  const prefix = `member-${index}`
  return (
    <article aria-labelledby={`${prefix}-title`} className="space-y-6 rounded-2xl border p-4 md:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id={`${prefix}-title`} className="text-xl font-semibold">
          {member.label}
        </h2>
        <Badge variant="secondary">{member.role}</Badge>
      </div>
      <BehaviourOverviewView
        insight={member.insight}
        periods={member.months.map((m) => m.period)}
        loading={false}
        error={null}
        onRetry={() => {}}
        idPrefix={`${prefix}-overview`}
        heading={`${member.label}: financial behaviour overview`}
      />
      <section aria-labelledby={`${prefix}-months-heading`} className="space-y-2">
        <h3 id={`${prefix}-months-heading`} className="text-base font-semibold">
          {member.label}: monthly records
        </h3>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Income, spending and savings by month</CardTitle>
            <CardDescription>Fictional amounts in rupees; the table gives the same values and the changes worked out from them.</CardDescription>
          </CardHeader>
          <CardContent>
            <MemberMonths member={member} index={index} />
          </CardContent>
        </Card>
      </section>
      <div className="grid gap-6 md:grid-cols-2">
        <InvestmentBehaviourView
          behaviour={investmentBehaviour({ findings: member.insight.behaviour.findings })}
          loading={false}
          idPrefix={`${prefix}-investment`}
          heading={`${member.label}: investment behaviour`}
        />
        <SpendingPatternView state={DEMO_SPENDING_STATE} idPrefix={`${prefix}-spending`} heading={`${member.label}: spending pattern`} />
      </div>
      <SectionUnavailable title={INDIVIDUAL_COMMITMENTS_TITLE} message={INDIVIDUAL_COMMITMENTS_MESSAGE} />
    </article>
  )
}

export interface DemoFamilyViewProps extends Omit<BehaviourSentimentViewProps, "data" | "error" | "loading" | "plainLanguage" | "noteOnly" | "modelState"> {
  data: Family | undefined
  loading: boolean
  error: unknown
  examples: readonly DemoExample[]
  onUseExample: (text: string) => void
}

/**
 * The family demonstration as pure markup: the banner, one section per fictional member, the household's own totals (the real household engine over invented records, shown by the same view as
 * the stored-records summary) and the primary member's optional note. DISPLAY ONLY: every figure and sentence is the backend's; a failure shows an error and no demo figures.
 */
export function DemoFamilyView({ data, loading, error, examples, onUseExample, ...note }: DemoFamilyViewProps) {
  if (error) {
    return (
      <div className="space-y-6">
        <FamilyDemoBanner />
        <DemoErrorState error={error} onRetry={note.onRetry} />
      </div>
    )
  }
  if (loading && !data) {
    return (
      <div className="space-y-6" aria-busy="true">
        <FamilyDemoBanner />
        <LoadingState label="Loading the family demonstration data" />
      </div>
    )
  }
  if (!data) return <FamilyDemoBanner />
  const primary = data.members[0]
  return (
    <div className="space-y-8">
      <FamilyDemoBanner notice={data.notice} />
      <section aria-labelledby="family-members-heading" className="space-y-2">
        <h2 id="family-members-heading" className="text-lg font-semibold">
          {data.household_label}: {data.members.length} members
        </h2>
        <p className="text-muted-foreground text-sm">Each member's figures come from that member's own reported months. The household totals below come from the household's own records.</p>
      </section>
      {data.members.map((member, index) => (
        <MemberSection key={member.label} member={member} index={index} />
      ))}
      <section aria-labelledby="family-household-heading" className="space-y-3">
        <h2 id="family-household-heading" className="text-lg font-semibold">
          Household totals (fictional)
        </h2>
        <p className="text-muted-foreground text-sm">
          These totals, including the household's loans and EMIs, are worked out from the household's own income, spending, asset and liability records. They are not the members' months added
          together. A loan with no stated payment is shown as not provided, never as zero.
        </p>
        <HouseholdFinancialSummaryView summary={data.household_summary} />
      </section>
      {primary ? (
        <section aria-labelledby="family-note-heading" className="space-y-3">
          <h2 id="family-note-heading" className="text-lg font-semibold">
            Optional written note ({primary.label})
          </h2>
          <DemoExamples examples={examples} onUseExample={onUseExample} />
          <BehaviourSentimentView {...note} data={primary.insight} loading={false} error={undefined} plainLanguage noteOnly modelState={data.sentiment_model.state} />
        </section>
      ) : null}
    </div>
  )
}
