import { CheckCircle2, GraduationCap, Info } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { OnboardingNoProfile } from "@/components/shell/onboarding-no-profile"
import { OnboardingSteps } from "@/components/shell/onboarding-steps"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  useQuestionnaireAnswersQuery,
  useQuestionnaireQuery,
  useSubmitQuestionnaireAnswers,
} from "@/hooks/use-questionnaire"
import { useCustomer } from "@/providers/customer-context"

/**
 * `/onboarding/questionnaire` -- Phase 22 built this page against a
 * non-persisting backend; Phase 23 adds the real persistence that was
 * missing then. Every section/question/option still comes from
 * `GET /api/questionnaire` (Phase 15's parser of `datasets/raw/FAR-Trans/
 * questionnaires.csv`) -- none is hard-coded.
 *
 * Answers now round-trip through `POST`/`GET
 * /api/profiles/{id}/questionnaire` (Phase 23): on load, any previously
 * saved answers (`useQuestionnaireAnswersQuery`) preselect the matching
 * radio buttons; "Save & Continue to Goals" submits the current answer
 * set and navigates only in the mutation's `onSuccess` callback, so a
 * failed save never silently proceeds as if it had worked. Re-submitting
 * an already-answered question is a real backend UPDATE, not a duplicate
 * (enforced server-side by `uq_questionnaire_answers_customer_question`).
 *
 * No question is required by the schema, so a user may also continue with
 * zero answers -- in that case nothing is submitted (there is nothing
 * valid to submit) and the page just navigates on, never claiming a save
 * that didn't happen.
 *
 * No score, risk category, or suitability inference is computed anywhere
 * in this file -- selecting an option only ever updates which key is
 * recorded as this question's local answer, and the API call below only
 * ever forwards `{question_number, option_key}` pairs.
 */
export function OnboardingQuestionnairePage() {
  const navigate = useNavigate()
  const location = useLocation()
  // Where "Back" goes: the page that linked here (Customer Profile passes it in
  // router state); the account-creation flow, which replaces its own history
  // entry, has no such state and returns to /create-user as before.
  const backTo = (location.state as { from?: string } | null)?.from ?? "/create-user"
  const { profileId } = useCustomer()
  const query = useQuestionnaireQuery()
  const answersQuery = useQuestionnaireAnswersQuery(profileId)
  const submitMutation = useSubmitQuestionnaireAnswers(profileId)

  const [answers, setAnswers] = useState<Record<number, string>>({})
  const hasPreselected = useRef(false)

  useEffect(() => {
    if (hasPreselected.current || !answersQuery.data) return
    hasPreselected.current = true
    const preselected: Record<number, string> = {}
    for (const answer of answersQuery.data.answers) {
      preselected[answer.question_number] = answer.option_key
    }
    setAnswers(preselected)
  }, [answersQuery.data])

  const handleContinue = () => {
    const answerList = Object.entries(answers).map(([questionNumber, optionKey]) => ({
      question_number: Number(questionNumber),
      option_key: optionKey,
    }))

    if (answerList.length === 0) {
      navigate("/onboarding/goals")
      return
    }

    submitMutation.mutate(
      { answers: answerList },
      { onSuccess: () => navigate("/onboarding/goals") },
    )
  }

  return (
    <div className="bg-background min-h-svh p-6 md:p-10">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        <div className="flex items-center gap-2">
          <div className="bg-primary text-primary-foreground flex size-6 items-center justify-center rounded-md">
            <GraduationCap className="size-4" />
          </div>
          <span className="font-medium">WealthPilot AI</span>
        </div>

        <OnboardingSteps current="questionnaire" />

        {profileId === null ? (
          <OnboardingNoProfile />
        ) : (
          <>
            <div className="space-y-1">
              <h1 className="text-2xl font-bold">Risk &amp; Investment Questionnaire</h1>
              <p className="text-muted-foreground text-sm">
                Answer a few questions to help WealthPilot understand your investment
                preferences.
              </p>
            </div>

            <Alert>
              <Info />
              <AlertTitle>Your answers are saved to your profile</AlertTitle>
              <AlertDescription>
                Selecting an option and continuing stores your answer against this profile.
                Your risk category is determined separately, from your actual transaction
                history, by WealthPilot's risk model — answering these questions does not
                change it.
              </AlertDescription>
            </Alert>

            {submitMutation.isError ? (
              <ErrorState error={submitMutation.error} onRetry={() => submitMutation.reset()} />
            ) : null}

            {submitMutation.isSuccess ? (
              <Alert>
                <CheckCircle2 />
                <AlertTitle>Answers saved</AlertTitle>
                <AlertDescription>Your questionnaire answers were saved to your profile.</AlertDescription>
              </Alert>
            ) : null}

            {query.isLoading || answersQuery.isLoading ? (
              <LoadingState label="Loading questionnaire" />
            ) : query.error ? (
              <ErrorState error={query.error} onRetry={() => query.refetch()} />
            ) : answersQuery.error ? (
              <ErrorState error={answersQuery.error} onRetry={() => answersQuery.refetch()} />
            ) : !query.data || query.data.sections.length === 0 ? (
              <Card>
                <CardContent className="text-muted-foreground pt-6 text-sm">
                  The questionnaire is currently unavailable.
                </CardContent>
              </Card>
            ) : (
              <div className="flex flex-col gap-4">
                {query.data.sections.map((section) => (
                  <Card key={section.name}>
                    <CardHeader>
                      <CardTitle>{section.name}</CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-6">
                      {section.questions.map((question) => (
                        <fieldset key={question.number} className="flex flex-col gap-2">
                          <legend className="text-sm font-medium">
                            {question.number}. {question.text}
                          </legend>
                          <RadioGroup
                            value={answers[question.number] ?? null}
                            onValueChange={(value) =>
                              setAnswers((prev) => ({ ...prev, [question.number]: value ?? "" }))
                            }
                          >
                            {question.options.map((option) => {
                              const inputId = `q${question.number}-${option.key}`
                              return (
                                <div key={option.key} className="flex items-center gap-2">
                                  <RadioGroupItem value={option.key} id={inputId} />
                                  <Label htmlFor={inputId} className="font-normal">
                                    {option.text}
                                  </Label>
                                </div>
                              )
                            })}
                          </RadioGroup>
                        </fieldset>
                      ))}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2">
              <Button variant="outline" render={<Link to={backTo} />}>
                Back
              </Button>
              <Button onClick={handleContinue} disabled={submitMutation.isPending}>
                {submitMutation.isPending ? "Saving…" : "Save & Continue to Goals"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
