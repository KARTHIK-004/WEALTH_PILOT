import { RiskProbabilityChart } from "@/components/charts/risk-probability-chart"
import { ErrorState } from "@/components/shell/error-state"
import { TermLabel } from "@/components/shell/help-tip"
import { LoadingState } from "@/components/shell/loading-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { formatPercent } from "@/lib/format"
import { HELP, getRiskCategoryDescription } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

const TITLE = "Risk Profile"
const DESCRIPTION = "This assessment estimates which risk category best matches your financial profile."

/**
 * Every value here comes directly from `AnalysisResult.risk` (Phase 4's
 * classifier output, unmodified). No risk category is ever computed or
 * guessed in React (section 14) and no confidence score is invented when
 * the API doesn't provide one (section 15) — `confidence`/
 * `class_probabilities` are rendered only when actually present.
 * Phase 25: the card description says plainly that this is the model's own
 * output, not something derived from the questionnaire.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): each category
 * gets an everyday description (explanatory only -- the model's classes are
 * unchanged), the probabilities are called the model's estimated confidence
 * and explicitly NOT percentages of anyone's money, and the model version
 * and artifact path ("models/risk") sit in Analysis information / Technical
 * details instead of the main view.
 */
export function RiskAssessmentPage() {
  const { profileId } = useCustomer()
  const query = useAnalysisQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title={TITLE} description={DESCRIPTION}>
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const risk = query.data?.risk

  return (
    <PageContainer title={TITLE} description={DESCRIPTION}>
      {query.isLoading ? (
        <LoadingState label="Assessing your risk profile" />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : !risk || !risk.risk_category ? (
        <Card>
          <CardHeader>
            <CardTitle>Your risk profile</CardTitle>
          </CardHeader>
          <CardContent>
            <SectionUnavailable
              title="Risk profile not available yet"
              message="The risk assessment needs investment-history information that is not available for this profile yet. No risk profile is assumed, so the rest of the analysis waits for this information."
              reason={risk?.unavailable_reason}
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>
                <TermLabel help={HELP.riskProfile}>Your risk profile</TermLabel>
              </CardTitle>
              <CardDescription>
                Classified by the risk assessment model from this profile's investment history — not calculated
                from questionnaire answers.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Badge className="text-sm">{risk.risk_category}</Badge>
                {getRiskCategoryDescription(risk.risk_category) ? (
                  <p className="text-sm">{getRiskCategoryDescription(risk.risk_category)}</p>
                ) : null}
              </div>

              {risk.confidence !== null && risk.confidence !== undefined ? (
                <div className="max-w-sm space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className="text-muted-foreground">
                      <TermLabel help={HELP.riskConfidence}>How confident the assessment is</TermLabel>
                    </span>
                    <span className="font-medium">{formatPercent(risk.confidence)}</span>
                  </div>
                  <Progress value={risk.confidence * 100} aria-label="How confident the risk assessment is" />
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Estimated risk profile</CardTitle>
              <CardDescription>
                These percentages represent the model's estimated confidence across the available risk categories.
                They are not percentages of your money. The darker bar is the category the model selected.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {risk.class_probabilities ? (
                <div className="grid items-center gap-4 lg:grid-cols-2">
                  <RiskProbabilityChart
                    probabilities={risk.class_probabilities}
                    selectedCategory={risk.risk_category}
                  />
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Risk category</TableHead>
                        <TableHead className="text-right">Estimated confidence</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {Object.entries(risk.class_probabilities).map(([category, probability]) => (
                        <TableRow key={category}>
                          <TableCell>
                            {getRiskCategoryDescription(category) ? (
                              <TermLabel help={getRiskCategoryDescription(category) as string}>{category}</TermLabel>
                            ) : (
                              category
                            )}
                          </TableCell>
                          <TableCell className="text-right">{formatPercent(probability, 1)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <RiskProbabilityChart probabilities={null} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>What the risk categories mean</CardTitle>
              <CardDescription>Explanations only — they do not change the model's result.</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                {Object.keys(risk.class_probabilities ?? { [risk.risk_category]: 1 }).map((category) => (
                  <div key={category}>
                    <dt className="font-medium">{category}</dt>
                    <dd className="text-muted-foreground">{getRiskCategoryDescription(category) ?? "No description available."}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Analysis information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <dl className="grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground text-xs">Assessment</dt>
                  <dd>Risk assessment model</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">Model version</dt>
                  <dd>{risk.model_version ?? "Not provided"}</dd>
                </div>
              </dl>
              <TechnicalDetails
                items={[
                  { label: "Model version", value: risk.model_version },
                  { label: "Model artifact (data source)", value: risk.data_source },
                  { label: "Raw confidence", value: risk.confidence },
                ]}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  )
}
