import { ArrowLeftRight, CircleHelp, Frown, Info, Meh, Scale, Smile } from "lucide-react"

import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "cn"
import {
  CONFIDENCE_NOT_AVAILABLE,
  FALLBACK_MESSAGE,
  INFORMATIONAL_NOTICE,
  INTERPRETATION_NOTICE,
  NO_CONFIDENCE_EXPLANATION,
  NO_TEXT_MESSAGE,
  PREFERENCE_NOTICE,
  calibrationLabel,
  describeConfidence,
  describeIntensity,
  describeMethodUsed,
  describeReadingStatus,
  describeSentiment,
  fallbackReasonLabel,
  methodLabel,
  orderedProbabilities,
  preferenceLabel,
  relevanceLabel,
  toneLabel,
  topicLabel,
  validationLabel,
  type ReadingStatus,
  type SentimentPresentation,
} from "@/lib/user-text-input"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]
type Sentiment = components["schemas"]["UserSentimentOut"]

const SENTIMENT_ICON: Record<SentimentPresentation["icon"], typeof Smile> = {
  positive: Smile,
  negative: Frown,
  neutral: Meh,
  mixed: ArrowLeftRight,
  uncertain: CircleHelp,
  unknown: CircleHelp,
}

/**
 * The headline of a reading. A reading that found a sentiment has a solid border; one that did not (`uncertain`, `insufficient_evidence`, or a value the UI does not know) has a dashed border,
 * muted text and says so in words, so an inconclusive result is never mistaken for a confirmed one and never shown as neutral. Meaning is carried by the icon and the words, not by colour alone.
 */
function ReadingHeadline({ sentiment }: { sentiment: Sentiment }) {
  const presentation = describeSentiment(sentiment.sentiment)
  const Icon = SENTIMENT_ICON[presentation.icon]
  return (
    <div
      data-reading={presentation.inconclusive ? "inconclusive" : "found"}
      className={cn("flex items-start gap-3 rounded-lg border p-3", presentation.inconclusive ? "text-muted-foreground border-dashed" : "bg-muted/40")}
    >
      <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-md border", presentation.inconclusive ? "border-dashed" : "bg-background")}>
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <div className="min-w-0 space-y-0.5">
        <p className={cn("text-sm font-medium", presentation.inconclusive ? "" : "text-foreground")}>Sentiment: {presentation.label}</p>
        <p className="text-sm">{presentation.explanation}</p>
        {presentation.inconclusive ? <p className="text-xs">Not a confirmed reading.</p> : null}
      </div>
    </div>
  )
}

/** Which of the interpretation states this is, in words: valid, weak, abstained. A weak or abstained reading is dashed, so it is never mistaken for a valid one. */
function StateBanner({ status }: { status: ReadingStatus }) {
  return (
    <div data-state={status.kind} className={cn("flex flex-wrap items-start gap-x-3 gap-y-1 rounded-lg border p-3 text-sm", status.kind === "valid" ? "bg-muted/40" : "border-dashed")}>
      <Badge variant={status.kind === "valid" ? "secondary" : "outline"} className={status.kind === "valid" ? "" : "border-dashed"}>
        {status.label}
      </Badge>
      <p className="min-w-0 flex-1 basis-60 [overflow-wrap:anywhere]">{status.message}</p>
    </div>
  )
}

function Facets({ sentiment, status }: { sentiment: Sentiment; status: ReadingStatus }) {
  const interpreted = status.kind !== "abstained"
  const methodUsed = describeMethodUsed(sentiment)
  return (
    <dl className="grid gap-x-4 gap-y-3 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]">
      <dt className="text-muted-foreground">Financial relevance</dt>
      <dd>{relevanceLabel(sentiment.financial_relevance)}</dd>
      <dt className="text-muted-foreground">Emotional tone</dt>
      <dd>
        {sentiment.emotional_tone ? (
          <span>
            {toneLabel(sentiment.emotional_tone)}
            {interpreted ? <span className="text-muted-foreground"> (from explicit words in your text; this is not a measure of how much risk you can take)</span> : null}
          </span>
        ) : (
          <span className="text-muted-foreground">Not available</span>
        )}
      </dd>
      <dt className="text-muted-foreground">Topics named</dt>
      <dd>
        {sentiment.topics.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Topics named in your text">
            {sentiment.topics.map((topic) => (
              <li key={topic}>
                <Badge variant="outline">{topicLabel(topic)}</Badge>
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-muted-foreground">None named</span>
        )}
      </dd>
      <dt className="text-muted-foreground">Confidence</dt>
      <dd className="text-muted-foreground" aria-label={sentiment.confidence === null ? CONFIDENCE_NOT_AVAILABLE : undefined}>
        {describeConfidence(sentiment.confidence, sentiment.confidence_band)}
        {sentiment.confidence === null ? <span> &mdash; {NO_CONFIDENCE_EXPLANATION}</span> : null}
        {sentiment.confidence_calibration_status !== "not_applicable" ? <span> ({calibrationLabel(sentiment.confidence_calibration_status)})</span> : null}
      </dd>
      {sentiment.class_probabilities ? (
        <>
          <dt className="text-muted-foreground">Class probabilities</dt>
          <dd>
            <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Class probabilities from the model">
              {orderedProbabilities(sentiment.class_probabilities).map((item) => (
                <li key={item.code}>
                  {item.label} {item.value}
                </li>
              ))}
            </ul>
          </dd>
        </>
      ) : null}
      <dt className="text-muted-foreground">Sentiment intensity</dt>
      <dd className="text-muted-foreground">{describeIntensity(sentiment.sentiment_intensity)}</dd>
      <dt className="text-muted-foreground">Method used</dt>
      <dd data-method={methodUsed.kind}>
        <span className="font-medium">{methodUsed.label}</span>
        <span className="text-muted-foreground">
          {" "}
          &middot; {methodLabel(sentiment.method)}
          {sentiment.model_name ? `; model ${sentiment.model_name}` : ""} ({sentiment.model_version})
        </span>
      </dd>
      {sentiment.fallback_used ? (
        <>
          <dt className="text-muted-foreground">Why the rules answered</dt>
          <dd>{fallbackReasonLabel(sentiment.fallback_reason)}</dd>
        </>
      ) : null}
      <dt className="text-muted-foreground">Validation status</dt>
      <dd>{validationLabel(sentiment.validation_status)}</dd>
      {sentiment.rules_baseline && (sentiment.method !== "rules_baseline" || sentiment.disagreement) ? (
        <>
          <dt className="text-muted-foreground">Rules baseline reading</dt>
          <dd>
            {describeSentiment(sentiment.rules_baseline.label).label}
            <span className="text-muted-foreground"> ({sentiment.rules_baseline.model_version}, kept for comparison)</span>
          </dd>
        </>
      ) : null}
    </dl>
  )
}

function Quote({ children }: { children: string }) {
  return <p className="text-muted-foreground border-l-2 pl-3 text-sm italic [overflow-wrap:anywhere]">&ldquo;{children}&rdquo;</p>
}

function Preferences({ sentiment, confirmation }: { sentiment: Sentiment; confirmation: string }) {
  return (
    <div className="space-y-2" role="group" aria-label="Possible preferences">
      <p className="text-sm font-medium">Possible preferences</p>
      {sentiment.preferences.length > 0 ? (
        <>
          <ul className="space-y-2">
            {sentiment.preferences.map((preference) => (
              <li key={preference.code} className="space-y-1 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="border-dashed">
                    Unconfirmed
                  </Badge>
                  <span className="font-medium">{preferenceLabel(preference.code)}</span>
                </div>
                <Quote>{preference.evidence.phrase}</Quote>
              </li>
            ))}
          </ul>
          <p className="text-sm">{PREFERENCE_NOTICE}</p>
          <p className="text-muted-foreground text-xs">
            {confirmation} If this is not what you meant, change your text and press Analyse again.
          </p>
        </>
      ) : (
        <p className="text-muted-foreground text-sm">None inferred. A feeling is not treated as a preference, and nothing is guessed from weak wording.</p>
      )}
    </div>
  )
}

function Limits({ sentiment }: { sentiment: Sentiment }) {
  const baseline = sentiment.method === "rules_baseline" || sentiment.method === "unavailable"
  return (
    <Alert>
      <Info aria-hidden="true" />
      <AlertTitle>{baseline ? "A simple automatic reading, not a validated model" : "An automatic reading, not a fact about you"}</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>
          {baseline
            ? "This reading follows a small fixed set of rules. It is not a trained or validated model, it reports no confidence level, and it is a suggestion, not a fact about you. "
            : "This reading is a suggestion, not a fact about you. "}
          Your feelings are not your risk tolerance, and nothing here changes your risk profile or your recommendations.
        </p>
        {sentiment.limitations.length > 0 ? (
          <ul className="list-disc space-y-0.5 pl-5" aria-label="Limits of this reading">
            {sentiment.limitations.map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}

function Reading({ sentiment, status, preferenceConfirmation }: { sentiment: Sentiment; status: ReadingStatus; preferenceConfirmation: string }) {
  return (
    <div className="space-y-4">
      {status.fallback ? (
        <Alert data-fallback="rules">
          <Info aria-hidden="true" />
          <AlertDescription>
            {FALLBACK_MESSAGE} <span className="text-muted-foreground">({fallbackReasonLabel(sentiment.fallback_reason)}.)</span>
          </AlertDescription>
        </Alert>
      ) : null}
      {sentiment.disagreement ? (
        <Alert data-disagreement="true">
          <Scale aria-hidden="true" />
          <AlertTitle>The model and the rules baseline read this text differently</AlertTitle>
          <AlertDescription>Both readings are shown. Neither is a fact about you, and neither changes your risk profile.</AlertDescription>
        </Alert>
      ) : null}
      <StateBanner status={status} />
      <ReadingHeadline sentiment={sentiment} />
      <Facets sentiment={sentiment} status={status} />

      {sentiment.evidence.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-sm font-medium">Evidence: the words this reading is based on</p>
          <ul className="space-y-1.5">
            {sentiment.evidence.map((item) => (
              <li key={`${item.label}-${item.phrase}`}>
                <Quote>{item.phrase}</Quote>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <Preferences sentiment={sentiment} confirmation={preferenceConfirmation} />
      <Limits sentiment={sentiment} />
      <p className="text-muted-foreground text-xs">{INTERPRETATION_NOTICE}</p>
    </div>
  )
}

/** A disagreement between what the words suggest and the stored assessment: both are named, the stored assessment is stated to remain authoritative, and the inference is unconfirmed. */
function Conflicts({ conflicts }: { conflicts: Insight["conflicts"] }) {
  if (conflicts.length === 0) return null
  return (
    <Alert data-conflict="true">
      <Scale aria-hidden="true" />
      <AlertTitle>Your words and your risk assessment differ</AlertTitle>
      <AlertDescription className="space-y-3">
        <ul className="space-y-3">
          {conflicts.map((conflict) => (
            <li key={conflict.code} className="space-y-1">
              <p>{conflict.detail}</p>
              <dl className="grid gap-x-3 gap-y-0.5 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]">
                <dt className="text-muted-foreground">Suggested by your words</dt>
                <dd>
                  {preferenceLabel(conflict.inferred_preference)} <span className="text-muted-foreground">(unconfirmed)</span>
                </dd>
                <dt className="text-muted-foreground">Stored assessment</dt>
                <dd>
                  {conflict.stored_category} <span className="text-muted-foreground">(remains authoritative; source: {conflict.authoritative_source})</span>
                </dd>
                <dt className="text-muted-foreground">What you can do</dt>
                <dd>Confirm or correct this interpretation. Until then it changes nothing.</dd>
              </dl>
            </li>
          ))}
        </ul>
        <p>Your existing risk assessment stays the authority. Your words do not change it.</p>
      </AlertDescription>
    </Alert>
  )
}

/**
 * "How your words read": the backend's interpretation of the optional text. DISPLAY ONLY (ADR-043, ADR-048, ADR-050): every label, topic, preference and phrase is the backend's. No confidence
 * is shown unless the backend gives one, `uncertain` and `insufficient_evidence` are never turned into `neutral`, an abstention is stated in words and shows no sentiment, a weak reading is
 * marked as weak, a fallback to the rules baseline is announced, and when the words differ from the stored assessment the page says the stored assessment remains the authority.
 */
export function SentimentResultsPanel({ data }: { data: Insight }) {
  const sentiment = data.user_sentiment
  const status = describeReadingStatus(sentiment)
  return (
    <Card role="region" aria-labelledby="reading-heading">
      <CardHeader>
        <CardTitle id="reading-heading" role="heading" aria-level={2} className="text-base">
          How your words read
        </CardTitle>
        <CardDescription>An automatic suggestion about the text you wrote, for you to confirm. It is not a fact about you.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert data-notice="informational">
          <Info aria-hidden="true" />
          <AlertDescription>{INFORMATIONAL_NOTICE}</AlertDescription>
        </Alert>

        {status.kind === "no_text" ? (
          <SectionUnavailable title="No reading shown" message={`You have not written anything. ${NO_TEXT_MESSAGE}`} reason={sentiment.unavailable_reason} />
        ) : (
          <Reading sentiment={sentiment} status={status} preferenceConfirmation={data.preference_confirmation} />
        )}

        <Conflicts conflicts={data.conflicts} />
      </CardContent>
    </Card>
  )
}
