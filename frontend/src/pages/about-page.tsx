import {
  Activity,
  ArrowRight,
  Ban,
  CheckCircle2,
  Database,
  Dices,
  FlaskConical,
  Gauge,
  HeartPulse,
  Home,
  Layers,
  Lightbulb,
  PieChart,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
  Users,
} from "lucide-react"

import { AboutSection, Callout, DataTable, EquationRow, FlowSteps, InfoCard, Takeaway } from "@/components/about/about-ui"
import { HomeFooter } from "@/components/home/home-footer"
import { HomeNavbar } from "@/components/home/home-navbar"
import { scrollToSection } from "@/components/home/section-nav"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"

/**
 * About This Project (`/about`) -- explains WealthPilot AI to a visitor, an
 * M.Tech guide and a technical reviewer on the same page.
 *
 * Design principle: every section shows a SIMPLE explanation by default, with
 * the exact numbers, dataset details and implementation specifics one click
 * away in a collapsed "Technical details" (or similarly named) expandable --
 * never deleted, never summarised away. A short "Presentation takeaway" box
 * follows the page's most important sections, for a reader using this page
 * to run a viva.
 *
 * Every figure, named anywhere on this page (visible or collapsed), is a
 * documented project result, carried over unchanged from this page's own
 * prior, repository-verified version -- never recomputed in React, never
 * rounded in a way that changes its meaning: `models/metrics.json` (risk,
 * expense, behaviour, market, portfolio), `reports/phase2_data_quality_report.md`
 * (dataset counts), `reports/phase3_leakage_audit.md` (leakage fix),
 * `core/goals.py` (goal engine settings), `agents/graph.py` (routing),
 * `reports/final_viva_facts.md` (AutoGen status). No customer record or
 * internal id appears on this page.
 */

const SECTIONS = [
  { id: "overview", title: "Project Overview" },
  { id: "problem", title: "Problem Statement" },
  { id: "objectives", title: "Project Objectives" },
  { id: "how-it-works", title: "How WealthPilot AI Works" },
  { id: "architecture", title: "System Architecture" },
  { id: "datasets", title: "Data Sources" },
  { id: "preparation", title: "Data Preparation" },
  { id: "ml-modules", title: "Machine Learning Modules" },
  { id: "comparison", title: "Algorithm Comparison" },
  { id: "why-selected", title: "Why These Methods" },
  { id: "pipeline", title: "Financial Analysis Pipeline" },
  { id: "portfolio", title: "Portfolio Analysis" },
  { id: "goals", title: "Goal Planning" },
  { id: "agents", title: "Agentic AI" },
  { id: "compliance", title: "Compliance" },
  { id: "household", title: "Individual + Household" },
  { id: "stack", title: "Technology Stack" },
  { id: "results", title: "Key Results" },
  { id: "integrity", title: "Data Integrity" },
  { id: "limitations", title: "Limitations" },
  { id: "technical-summary", title: "Technical Summary & References" },
] as const

const n = (id: (typeof SECTIONS)[number]["id"]) => SECTIONS.findIndex((s) => s.id === id) + 1

function List({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  )
}

export function AboutPage() {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col">
      <a
        href="#about-main"
        className="bg-background focus-visible:ring-ring/50 sr-only z-50 rounded-md text-sm focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:border focus:px-3 focus:py-2 focus-visible:ring-3"
      >
        Skip to content
      </a>
      <HomeNavbar />
      <main id="about-main" className="mx-auto w-full max-w-6xl flex-1 space-y-16 px-4 py-12 md:px-6 md:py-16">
        {/* Hero -- unnumbered, deliberately brief */}
        <section aria-labelledby="hero-heading" className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">Educational decision-support prototype</Badge>
            <Badge variant="outline">M.Tech project</Badge>
          </div>
          <h1 id="hero-heading" className="text-4xl font-semibold tracking-tight text-balance md:text-5xl">
            About WealthPilot AI
          </h1>
          <p className="text-primary text-lg font-medium text-pretty">
            An Agentic AI-Based Financial Planning and Decision-Support Prototype
          </p>
          <p className="text-muted-foreground max-w-3xl text-lg text-pretty">
            WealthPilot combines financial analysis, machine learning, goal planning, portfolio analysis and
            compliance checks in one workflow. It then explains the results in simple language.
          </p>
          <FlowSteps
            label="What WealthPilot does, in one line"
            steps={[
              { title: "Financial Data" },
              { title: "Analysis" },
              { title: "Risk & Goals" },
              { title: "Portfolio" },
              { title: "Compliance" },
              { title: "Explanation" },
            ]}
          />
        </section>

        <nav aria-label="On this page" className="bg-card rounded-xl border p-5">
          <h2 className="mb-3 text-sm font-medium">On this page</h2>
          <ol className="text-muted-foreground grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {SECTIONS.map((section, i) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  onClick={(event) => {
                    event.preventDefault()
                    scrollToSection(section.id)
                  }}
                  className="hover:text-foreground focus-visible:ring-ring/50 rounded-sm outline-none focus-visible:ring-3"
                >
                  {i + 1}. {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        {/* 1. Overview */}
        <AboutSection id="overview" number={n("overview")} title="Project Overview">
          <p className="text-muted-foreground max-w-3xl text-pretty">
            WealthPilot is a prototype that brings different parts of financial planning into one workflow. Instead
            of looking at risk, savings, goals and investments separately, the system analyses them together and
            explains the result in plain language. It never executes trades, moves money or connects to a brokerage.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              { icon: Gauge, title: "Risk", text: "Understand the user's risk category." },
              { icon: HeartPulse, title: "Financial Health", text: "Check savings and available financial information." },
              { icon: Target, title: "Goals", text: "Estimate whether goals are achievable." },
              { icon: PieChart, title: "Portfolio", text: "Analyse possible asset allocations." },
              { icon: Sparkles, title: "Explanation", text: "Explain the results in simple language." },
            ].map((card) => (
              <InfoCard key={card.title} icon={card.icon} title={card.title}>
                <p>{card.text}</p>
              </InfoCard>
            ))}
          </div>
          <Takeaway>One platform that combines financial analysis and explains the result.</Takeaway>
        </AboutSection>

        {/* 2. Problem */}
        <AboutSection id="problem" number={n("problem")} title="Problem Statement">
          <InfoCard icon={Lightbulb} title="The Problem">
            <p>Financial planning involves many separate questions:</p>
            <List
              items={[
                "What level of risk can I take?",
                "Is my emergency savings enough?",
                "Can I reach my goals?",
                "How could my money be allocated?",
                "Does the recommendation satisfy the rules?",
              ]}
            />
            <p>
              These questions are usually handled separately. WealthPilot connects them into one analysis workflow,
              and is open about where the available data cannot support an answer.
            </p>
          </InfoCard>
          <EquationRow
            parts={["Risk", "Financial Health", "Goals", "Portfolio", "Compliance"]}
            result="One Explainable Analysis"
          />
        </AboutSection>

        {/* 3. Objectives */}
        <AboutSection id="objectives" number={n("objectives")} title="Project Objectives">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { icon: Gauge, title: "Risk Assessment", text: "Identify the user's risk category using machine learning." },
              { icon: HeartPulse, title: "Financial Health", text: "Understand available income, expenses and savings information." },
              { icon: Activity, title: "Behaviour Analysis", text: "Detect unusual investment activity." },
              { icon: Target, title: "Goal Planning", text: "Estimate how likely financial goals are to be reached." },
              { icon: PieChart, title: "Portfolio Analysis", text: "Compare different ways of allocating investments." },
              { icon: Sparkles, title: "Explainable Recommendation", text: "Present the computed result in simple language." },
            ].map((card) => (
              <InfoCard key={card.title} icon={card.icon} title={card.title}>
                <p>{card.text}</p>
              </InfoCard>
            ))}
          </div>
          <TechnicalDetails
            items={[
              { label: "Risk categories", value: "Conservative, Income, Balanced, Aggressive (the model's own classes)" },
              { label: "Risk method", value: "A machine-learning classifier, trained offline" },
            ]}
          >
            <p className="text-muted-foreground">
              Two further objectives have their own full sections below rather than a card here: compliance
              validation (section {n("compliance")}, "{SECTIONS[n("compliance") - 1].title}") and individual/household
              support (section {n("household")}, "{SECTIONS[n("household") - 1].title}").
            </p>
          </TechnicalDetails>
        </AboutSection>

        {/* 4. How it works */}
        <AboutSection
          id="how-it-works"
          number={n("how-it-works")}
          title="How WealthPilot AI Works"
          intro="One analysis runs these steps in order, exactly as wired in the LangGraph workflow (agents/graph.py). Each step uses the results of the steps before it."
        >
          <FlowSteps
            label="How WealthPilot AI works, step by step"
            steps={[
              { title: "Your Information", icon: UserRound, text: "The profile, goals and financial details you provide." },
              { title: "Customer Analysis", icon: Users, text: "Loads your profile and goals into the analysis." },
              { title: "Risk Assessment", icon: Gauge, text: "Understands how comfortable you are with investment risk." },
              { title: "Financial Health", icon: HeartPulse, text: "Checks your income, spending and savings information." },
              { title: "Goal Analysis", icon: Target, text: "Estimates how achievable your financial goals are." },
              { title: "Market Analysis", icon: Activity, text: "Reviews recent market conditions." },
              { title: "Portfolio Construction", icon: PieChart, text: "Builds a possible investment mix for your risk profile." },
              { title: "Compliance Check", icon: ShieldCheck, text: "Confirms the plan meets the required safety rules." },
              { title: "Recommendation", icon: Lightbulb, text: "Combines everything into one recommended plan." },
              { title: "AI Explanation", icon: Sparkles, text: "Gemini turns the verified analysis results into an understandable explanation." },
              { title: "Personalized Plan", icon: CheckCircle2, text: "The plan and explanation you see on your dashboard." },
            ]}
          />
          <p className="text-muted-foreground text-sm">
            The backend calculates each result, following this fixed order. Gemini (AI Explanation) only turns the
            already-computed results into plain language — it does not calculate risk, portfolio weights, goal
            feasibility, compliance or the recommendation itself.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <InfoCard title="Low risk confidence">
              <p>→ Ask for more information.</p>
            </InfoCard>
            <InfoCard title="Low emergency savings">
              <p>→ Savings first.</p>
            </InfoCard>
            <InfoCard title="Compliance REJECT">
              <p>→ Stop the recommendation.</p>
            </InfoCard>
          </div>
          <TechnicalDetails
            items={[
              { label: "Implementation", value: "A LangGraph workflow of 14 steps with three decision points" },
              { label: "Risk confidence threshold", value: "0.50" },
              { label: "After compliance approves", value: "The recommendation engine, then the explanation step" },
            ]}
          />
          <Takeaway>Analyse → Check → Recommend → Explain.</Takeaway>
        </AboutSection>

        {/* 5. Architecture */}
        <AboutSection id="architecture" number={n("architecture")} title="System Architecture">
          <FlowSteps
            vertical
            label="System layers"
            steps={[
              { title: "User" },
              { title: "Frontend", detail: "React + TypeScript" },
              { title: "Backend", detail: "FastAPI + Analysis Services" },
              { title: "AI / ML / Financial Engines", detail: "ML Models + Financial Calculations" },
              { title: "Database", detail: "PostgreSQL + Model Artifacts" },
            ]}
          />
          <div className="space-y-3">
            <h3 className="font-semibold">Where does Gemini fit?</h3>
            <p className="text-muted-foreground">
              Gemini does not calculate financial numbers. The backend calculates the numbers first. Gemini receives
              those results and converts them into understandable explanations.
            </p>
            <FlowSteps
              label="How Gemini fits in"
              steps={[
                { title: "Backend calculates" },
                { title: "Computed results" },
                { title: "Gemini explains" },
                { title: "User sees explanation" },
              ]}
            />
          </div>
          <div className="space-y-3">
            <h3 className="font-semibold">Training vs. online serving</h3>
            <FlowSteps
              label="Model lifecycle"
              steps={[
                { title: "Training data" },
                { title: "Offline training", detail: "training/ scripts" },
                { title: "Model artifact", detail: "models/" },
                { title: "FastAPI startup", detail: "loaded and cached" },
                { title: "Online inference" },
              ]}
            />
            <p className="text-muted-foreground text-sm">
              Models are trained offline only. A request never trains or retrains a model.
            </p>
          </div>
          <TechnicalDetails
            items={[
              { label: "Analysis services", value: "Specifically a LangGraph workflow" },
              {
                label: "Structured-output validation",
                value:
                  "Gemini's output is validated against the backend's source numbers; if it does not match, or the service is unavailable, a templated restatement of the computed results is shown instead",
              },
            ]}
          />
        </AboutSection>

        {/* 6. Datasets */}
        <AboutSection
          id="datasets"
          number={n("datasets")}
          title="Data Sources"
          intro="Each dataset serves a different part of the system and is described separately."
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <InfoCard icon={Database} title="FAR-Trans">
              <p>Research financial/investment dataset.</p>
              <p className="text-foreground text-xs font-medium">Used for:</p>
              <List items={["Risk analysis", "Behaviour analysis", "Asset information"]} />
            </InfoCard>
            <InfoCard icon={FlaskConical} title="Kaggle Personal Finance Dataset">
              <p>Synthetic personal-finance dataset.</p>
              <p className="text-foreground text-xs font-medium">Used for:</p>
              <List items={["Expense segmentation experiment"]} />
            </InfoCard>
            <InfoCard icon={Activity} title="Market Data">
              <p>Historical market prices used for market analysis and portfolio-related calculations.</p>
            </InfoCard>
            <InfoCard icon={Database} title="Synthetic Demo Data">
              <p>Used only for application demonstrations and testing.</p>
              <p className="font-medium">Not used for model training.</p>
            </InfoCard>
          </div>
          <Callout icon={Layers} title="Separate populations — no customer-level linking">
            <FlowSteps
              label="FAR-Trans and Kaggle stay separate"
              steps={[{ title: "FAR-Trans" }, { title: "separate populations" }, { title: "Kaggle" }]}
            />
            <p className="text-muted-foreground">
              FAR-Trans provides real research data for customer, transaction, asset and market-related analysis but
              has no income, expense or savings fields. The Kaggle dataset provides the synthetic personal-finance
              variables needed for the expense-segmentation experiment. Kaggle data is never merged into FAR-Trans,
              and no customer from either dataset is linked to the other.
            </p>
          </Callout>
          <TechnicalDetails title="View dataset details">
            <div className="space-y-4">
              <p className="text-muted-foreground">
                Citation: J. Sanz-Cruzado, N. Droukas, R. McCreadie, “FAR-Trans: An Investment Dataset for Financial
                Asset Recommendation”, IJCAI-2024 Workshop on Recommender Systems in Finance (Fin-RecSys), CC-BY 4.0.
              </p>
              <DataTable
                caption="FAR-Trans files used (counts from reports/phase2_data_quality_report.md)"
                head={["File", "Size", "Coverage", "Role in WealthPilot"]}
                rows={[
                  ["customer_information.csv", "32,468 rows · 29,090 customers", "dated snapshots", "Risk labels (riskLevel), customer type and investment capacity"],
                  ["transactions.csv", "388,048 rows", "2 Jan 2018 – 30 Nov 2022", "Point-in-time behaviour features for the risk model; monthly behaviour panel"],
                  ["asset_information.csv", "836 rows · 806 unique ISINs", "—", "Asset metadata (asset class, sector) for portfolio-mix features"],
                  ["close_prices.csv", "703,303 rows · 807 ISINs", "1 Jan 2018 – 29 Nov 2022", "Point-in-time volatility and drawdown features"],
                  ["questionnaires.csv", "25 MiFID II questions with answer options", "—", "The in-app questionnaire. It contains no customer answers, so it is never a training feature"],
                ]}
              />
              <p className="text-muted-foreground">
                Genuine risk categories: Conservative, Income, Balanced, Aggressive. Rows labelled Predicted_* or
                Not_Available are another model's output, not ground truth, and are excluded from supervised labels.
                Genuine labelled data: 24,850 rows from 21,629 customers (21,528 after the leakage fix).
              </p>
              <p className="text-muted-foreground">
                Kaggle: miadul/personal-finance-ml-dataset — synthetic_personal_finance_dataset.csv, 32,424 rows.
              </p>
              <p className="text-muted-foreground">
                Market data: daily prices for five instruments (^IXIC, ^NDX, QQQ, AGG, GLD) retrieved with yfinance,
                from January 2022 to September 2026.
              </p>
              <p className="text-muted-foreground">
                Synthetic demo data is marked <code className="text-foreground">data_source = synthetic_demo</code>{" "}
                and <code className="text-foreground">training_eligible = false</code>.
              </p>
              <p className="text-muted-foreground">
                Not used by the models: markets.csv and limit_prices.csv (acquired and quality-checked only); the
                Kaggle alternative file personal_finance_tracker_dataset.csv (3,000 rows). datasets/raw/ is immutable
                — nothing in the application modifies it.
              </p>
            </div>
          </TechnicalDetails>
          <Takeaway>FAR-Trans and Kaggle are separate populations.</Takeaway>
        </AboutSection>

        {/* 7. Preparation */}
        <AboutSection id="preparation" number={n("preparation")} title="Data Preparation">
          <p className="text-muted-foreground max-w-3xl">
            Before training or analysis, the system cleans and prepares the data carefully.
          </p>
          <List
            items={[
              "Use genuine risk labels only",
              "Use information available at the correct time",
              "Prevent future information from entering training",
              "Fit preprocessing only on training data",
            ]}
          />
          <TechnicalDetails
            items={[
              { label: "Label filtering", value: "Predicted_* and Not_Available rows are excluded" },
              {
                label: "Point-in-time features",
                value: "Each customer's features use only transactions and prices dated on or before that customer's own label date",
              },
              { label: "Customers with no prior transactions", value: "Dropped rather than given invented values (101 of 21,629)" },
              {
                label: "Risk model preprocessing",
                value: "Numeric — median imputation then standard scaling; categorical — most-frequent imputation then one-hot encoding; fitted on training data only and saved with the model",
              },
              {
                label: "Expense features",
                value: "Income-normalised ratios on the Kaggle data, with the loan-repayment ratio log-transformed; standard scaling fitted before clustering",
              },
              { label: "Behaviour panel", value: "One row per customer per month; baselines use strictly earlier months only" },
              { label: "Market data", value: "Daily returns and 20-day volatility, scalers fitted on each training window only" },
            ]}
          />
        </AboutSection>

        {/* 8. ML modules */}
        <AboutSection id="ml-modules" number={n("ml-modules")} title="Machine Learning Modules">
          <DataTable
            caption="One method per problem, as implemented"
            head={["Problem", "Method", "Simple meaning"]}
            rows={[
              ["Risk", "Random Forest", "Uses many decision trees together"],
              ["Expense", "K-Means", "Groups similar spending patterns"],
              ["Behaviour", "Z-score + CUSUM + Isolation Forest", "Finds unusual activity"],
              ["Market", "Time-series models", "Studies market movements"],
              ["Goals", "Monte Carlo", "Tests many possible future paths"],
              ["Portfolio", "MVO / HRP / Equal Weight", "Builds different allocations"],
            ]}
          />
          <Takeaway>Different financial problems use different algorithms.</Takeaway>
        </AboutSection>

        {/* 9. Comparison */}
        <AboutSection
          id="comparison"
          number={n("comparison")}
          title="Algorithm Comparison"
          intro="Which algorithms were compared?"
        >
          <div className="grid gap-4 lg:grid-cols-2">
            <InfoCard icon={Gauge} title="Risk">
              <p>
                Logistic Regression vs Random Forest vs XGBoost vs MLP. Random Forest was selected based on the
                project's evaluation.
              </p>
              <p className="text-foreground font-semibold">Random Forest — Macro-F1: 0.4075 ± 0.0048</p>
              <TechnicalDetails title="View model comparison">
                <DataTable
                  caption="Macro-F1 (mean ± standard deviation across folds), 5-fold cross-validation"
                  head={["Model", "Macro-F1", "Notes"]}
                  rows={[
                    ["Random Forest", "0.4075 ± 0.0048", "Selected and served"],
                    ["XGBoost", "0.3969 ± 0.0075", "—"],
                    ["MLP (neural network)", "0.3545 ± 0.0094", "—"],
                    ["Logistic Regression", "0.3527 ± 0.0050", "—"],
                  ]}
                />
                <DataTable
                  caption="Random Forest per-class recall — how often examples of each class were correctly identified during evaluation"
                  head={["Risk category", "Recall"]}
                  rows={[
                    ["Conservative", "0.64"],
                    ["Income", "0.32"],
                    ["Balanced", "0.44"],
                    ["Aggressive", "0.42"],
                  ]}
                />
                <p className="text-muted-foreground mt-2">
                  These are modest scores, and performance differs between categories. They are evaluation results,
                  not customer financial outcomes.
                </p>
              </TechnicalDetails>
            </InfoCard>
            <InfoCard icon={Activity} title="Expense">
              <p>K-Means vs Ward vs Gaussian Mixture Model (GMM), k swept from 2 to 10.</p>
              <p className="text-foreground font-semibold">
                K-Means with k = 2 produced the highest silhouette score among the tested configurations.
              </p>
              <TechnicalDetails title="View model comparison">
                <DataTable
                  caption="Each method at its own best configuration"
                  head={["Method", "Best configuration", "Silhouette"]}
                  rows={[
                    ["K-Means", "k = 2", "0.458 (selected)"],
                    ["Ward hierarchical", "k = 2 (5,000-row subsample)", "0.407"],
                    ["Gaussian Mixture Model", "k = 10 (BIC-best, full covariance)", "0.013"],
                  ]}
                />
              </TechnicalDetails>
            </InfoCard>
            <InfoCard icon={ShieldCheck} title="Behaviour">
              <p>Three methods are used because they detect different types of unusual behaviour.</p>
              <List
                items={[
                  "Z-score → sudden unusual change",
                  "CUSUM → sustained change",
                  "Isolation Forest → unusual overall pattern",
                ]}
              />
              <TechnicalDetails title="View alert counts">
                <DataTable
                  caption="127,924 customer-months from 29,090 customers"
                  head={["Indicator", "Rolling z-score alerts", "CUSUM alarms"]}
                  rows={[
                    ["Monthly trade count", "5,114", "7,205"],
                    ["Monthly buy value", "5,543", "9,067"],
                  ]}
                />
                <p className="text-muted-foreground mt-2">
                  Isolation Forest flagged 6,397 customer-months (5.0%, its configured contamination rate).
                </p>
              </TechnicalDetails>
            </InfoCard>
            <InfoCard icon={Layers} title="Market">
              <p>
                ARIMA, LSTM and GRU were compared with a naive baseline. The tested models did not show statistically
                significant improvement over the baseline.
              </p>
              <TechnicalDetails
                items={[
                  { label: "Tests", value: "15 Diebold-Mariano tests (5 instruments × 3 models), all p > 0.05" },
                  { label: "Smallest p-value", value: "≈ 0.068" },
                ]}
              />
            </InfoCard>
          </div>
        </AboutSection>

        {/* 10. Why selected */}
        <AboutSection id="why-selected" number={n("why-selected")} title="Why These Methods">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <InfoCard icon={Gauge} title="Random Forest">
              <p>Works well with mixed customer profile features and combines many decision trees.</p>
              <TechnicalDetails items={[{ label: "Why Macro-F1", value: "All four risk categories matter equally; overall accuracy alone would favour the largest categories" }]} />
            </InfoCard>
            <InfoCard icon={Activity} title="K-Means">
              <p>Simple way to group customers with similar financial-ratio patterns.</p>
              <TechnicalDetails
                items={[
                  {
                    label: "The two groups",
                    value: "Differ mainly in leverage — about 88% with low debt/loan-repayment ratios, about 12% with much higher debt-to-income and repayment-to-income ratios; expense-to-income ratios are similar. Describes the Kaggle population only.",
                  },
                ]}
              />
            </InfoCard>
            <InfoCard icon={Layers} title="Behaviour Methods">
              <p>Different methods detect different types of unusual activity.</p>
            </InfoCard>
            <InfoCard icon={Dices} title="Monte Carlo">
              <p>Tests many possible paths instead of relying on one predicted future.</p>
            </InfoCard>
            <InfoCard icon={PieChart} title="Portfolio Methods">
              <p>Different allocation methods suit different risk categories.</p>
            </InfoCard>
            <InfoCard icon={ShieldCheck} title="Rule Engine">
              <p>Rules provide a clear and testable safety gate.</p>
            </InfoCard>
          </div>
        </AboutSection>

        {/* 11. Pipeline */}
        <AboutSection id="pipeline" number={n("pipeline")} title="Financial Analysis Pipeline">
          <FlowSteps
            vertical
            label="Pipeline"
            steps={[
              { title: "User Data" },
              { title: "Risk" },
              { title: "Financial Health" },
              { title: "Goals" },
              { title: "Portfolio" },
              { title: "Compliance" },
              { title: "Recommendation" },
              { title: "Explanation" },
            ]}
          />
          <div className="grid gap-3 sm:grid-cols-3">
            <InfoCard title="Not confident enough?">
              <p>Ask for more information.</p>
            </InfoCard>
            <InfoCard title="Emergency savings too low?">
              <p>Savings first.</p>
            </InfoCard>
            <InfoCard title="Compliance rejected?">
              <p>Stop the recommendation.</p>
            </InfoCard>
          </div>
          <TechnicalDetails
            items={[
              { label: "Implementation", value: "A LangGraph workflow of 14 steps with three decision points, followed by the recommendation engine and the explanation step" },
              { label: "Recommendation precedence", value: "Compliance → Savings first → Risk → Goals → Market (fixed order)" },
              { label: "Goal/market preferences", value: "Can only be recorded as matching or overridden; they never change the strategy chosen for the risk category" },
            ]}
          />
        </AboutSection>

        {/* 12. Portfolio */}
        <AboutSection id="portfolio" number={n("portfolio")} title="Portfolio Analysis">
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoCard title="Risk-Based Strategy">
              <p>Chooses the portfolio method according to the user's risk category.</p>
            </InfoCard>
            <InfoCard title="Mean-Variance Optimization">
              <p>Balances expected return and risk.</p>
            </InfoCard>
            <InfoCard title="Hierarchical Risk Parity">
              <p>Spreads risk across groups of assets.</p>
            </InfoCard>
            <InfoCard title="Equal Weight">
              <p>Divides the allocation equally.</p>
            </InfoCard>
          </div>
          <DataTable
            caption="Assets used in the implemented portfolio analysis"
            head={["Shown in the app as", "Ticker", "What it represents"]}
            rows={[
              ["Nasdaq-100 / US Growth", "QQQ", "Large non-financial companies listed on the Nasdaq-100"],
              ["US Bond Market", "AGG", "A diversified group of US bonds"],
              ["Gold", "GLD", "The price of gold"],
            ]}
          />
          <p className="text-muted-foreground text-sm">
            These are the assets used in this prototype's implemented portfolio analysis. They are not presented as
            universally suitable for every person.
          </p>
          <TechnicalDetails
            items={[
              { label: "Expected returns", value: "Annualised historical mean of daily simple returns (not a forecast)" },
              { label: "Covariance", value: "Ledoit-Wolf shrinkage, annualised" },
              { label: "MVO objective", value: "Maximise Sharpe ratio, risk-free rate 0" },
              { label: "Constraints", value: "Single-asset cap 70%; QQQ share band per risk category (e.g. Aggressive 55–80%)" },
              { label: "Backtest", value: "504-day lookback, rebalance every 63 days, no transaction costs" },
              {
                label: "Backtest Sharpe ratios",
                value: "1/N 1.6326 · HRP 1.0178 · MVO Conservative 1.7465 · Income 1.6522 · Balanced 1.5291 · Aggressive 1.7557",
              },
            ]}
          />
        </AboutSection>

        {/* 13. Goals */}
        <AboutSection id="goals" number={n("goals")} title="Goal Planning">
          <p className="text-muted-foreground max-w-3xl">
            We simulate many possible financial paths and count how often the goal is reached.
          </p>
          <FlowSteps
            label="How goal planning works"
            steps={[
              { title: "10,000 simulations" },
              { title: "Many possible paths" },
              { title: "Goal reached?" },
              { title: "Estimated success probability" },
            ]}
          />
          <DataTable
            caption="Feasibility labels on the estimated success probability"
            head={["Label", "Estimated success probability"]}
            rows={[
              ["Feasible", "80% or more"],
              ["At Risk", "50%–79%"],
              ["Not Feasible", "Below 50%"],
            ]}
          />
          <p className="text-muted-foreground text-sm">
            This is an estimate under stated assumptions, not a prediction of the future.
          </p>
          <TechnicalDetails
            items={[
              { label: "Simulations", value: "10,000 bootstrap paths" },
              { label: "Random seed", value: "42 (reproducible)" },
              { label: "Inputs", value: "Contribution, expected return and inflation supplied by the person; never assumed" },
            ]}
          />
        </AboutSection>

        {/* 14. Agents */}
        <AboutSection id="agents" number={n("agents")} title="Agentic AI" intro="Where is AI used?">
          <div className="grid gap-4 sm:grid-cols-3">
            <InfoCard icon={Layers} title="LangGraph">
              <p>Controls the analysis workflow.</p>
            </InfoCard>
            <InfoCard icon={Sparkles} title="Gemini">
              <p>Turns computed results into simple explanations.</p>
            </InfoCard>
            <InfoCard icon={Users} title="AutoGen">
              <p>Contains a tested strategy-debate module, but it is not currently used in the live analysis pipeline.</p>
            </InfoCard>
          </div>
          <Callout icon={Ban} title="Important">
            <p className="text-base font-semibold">AI does not calculate the financial numbers.</p>
            <FlowSteps
              label="Who does what"
              steps={[{ title: "Backend", detail: "calculates" }, { title: "Gemini", detail: "explains" }, { title: "Frontend", detail: "displays" }]}
            />
          </Callout>
          <TechnicalDetails title="What Gemini never does">
            <List
              items={[
                "Calculate portfolio allocations or returns",
                "Calculate risk probabilities",
                "Calculate emergency-fund amounts",
                "Decide any numerical financial value or override compliance",
              ]}
            />
            <p className="text-muted-foreground mt-2">
              The app shows each step's name, status and duration — never prompts or model reasoning. LangGraph is a
              fixed, acyclic graph of 14 steps with explicit routing and failure handling. AutoGen's built module
              debates with three LLM-backed agents (portfolio, risk and compliance).
            </p>
          </TechnicalDetails>
          <Takeaway>Backend calculates; Gemini explains.</Takeaway>
        </AboutSection>

        {/* 15. Compliance */}
        <AboutSection id="compliance" number={n("compliance")} title="Compliance" intro="Safety check before recommendation">
          <p className="text-muted-foreground max-w-3xl">
            Every recommendation passes through a rule-based compliance check. The system does not show a
            recommendation if it breaks the configured rules.
          </p>
          <FlowSteps label="Compliance gate" steps={[{ title: "Recommendation" }, { title: "Compliance Rules" }]} />
          <div className="grid gap-3 sm:grid-cols-2">
            <FlowSteps label="If the rules pass" steps={[{ title: "PASS" }, { title: "Continue" }]} />
            <FlowSteps
              label="If a rule is broken"
              steps={[{ title: "REJECT", tone: "destructive" }, { title: "Stop", tone: "destructive" }]}
            />
          </div>
          <p className="text-muted-foreground text-sm">
            This is a safety and control layer inside the prototype. It is not a regulatory certification.
          </p>
          <TechnicalDetails title="View the five rules">
            <p className="text-muted-foreground">
              Five REJECT-severity rules (version v1): the allocation adds up to 100%, no short positions, the
              Nasdaq-100 share stays within the band for the risk category, no single asset exceeds the cap, and
              savings come first when emergency savings are insufficient.
            </p>
          </TechnicalDetails>
          <Takeaway>Invalid recommendations are stopped before reaching the user.</Takeaway>
        </AboutSection>

        {/* 16. Household */}
        <AboutSection id="household" number={n("household")} title="Individual + Household">
          <div className="grid gap-4 md:grid-cols-2">
            <InfoCard icon={UserRound} title="Individual">
              <p>Analyses one person's:</p>
              <List items={["Risk", "Financial health", "Goals", "Portfolio", "Recommendation"]} />
            </InfoCard>
            <InfoCard icon={Home} title="Household">
              <p>Analyses shared:</p>
              <List items={["Income", "Expenses", "Assets", "Liabilities", "Goals", "Household financial summary"]} />
            </InfoCard>
          </div>
          <Callout icon={ShieldCheck} title="Individual and household calculations are kept separate">
            <p className="text-muted-foreground">
              No household figure feeds an individual analysis, and there is no household risk score or household
              recommendation.
            </p>
          </Callout>
        </AboutSection>

        {/* 17. Stack */}
        <AboutSection id="stack" number={n("stack")} title="Technology Stack">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { title: "Backend", items: ["Python", "FastAPI", "PostgreSQL"] },
              { title: "Machine Learning", items: ["scikit-learn", "XGBoost", "TensorFlow", "statsmodels", "arch"] },
              { title: "AI / Agents", items: ["LangGraph", "AutoGen", "Gemini"] },
              { title: "Frontend", items: ["React", "TypeScript", "Vite", "Tailwind CSS", "shadcn/ui"] },
            ].map((group) => (
              <InfoCard key={group.title} title={group.title}>
                <ul className="flex flex-wrap gap-1.5">
                  {group.items.map((item) => (
                    <li key={item}>
                      <Badge variant="outline">{item}</Badge>
                    </li>
                  ))}
                </ul>
              </InfoCard>
            ))}
          </div>
          <TechnicalDetails title="Full technical stack">
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                { title: "Backend (additional)", items: ["Python 3.11", "Pydantic v2", "SQLAlchemy", "Alembic"] },
                { title: "ML / data (additional)", items: ["SHAP", "pandas", "numpy", "scipy", "yfinance"] },
                { title: "AI / agents (additional)", items: ["Gemini API (google-genai)"] },
                { title: "Frontend (additional)", items: ["TanStack Query", "React Router", "Recharts", "lucide-react"] },
              ].map((group) => (
                <div key={group.title}>
                  <p className="text-foreground mb-1 font-medium">{group.title}</p>
                  <ul className="flex flex-wrap gap-1.5">
                    {group.items.map((item) => (
                      <li key={item}>
                        <Badge variant="outline">{item}</Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </TechnicalDetails>
        </AboutSection>

        {/* 18. Results */}
        <AboutSection id="results" number={n("results")} title="Key Results">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <InfoCard icon={Gauge} title="Risk Model">
              <p>Random Forest</p>
              <p className="text-foreground font-semibold">Macro-F1 ≈ 0.41</p>
            </InfoCard>
            <InfoCard icon={Activity} title="Expense Segmentation">
              <p>K-Means</p>
              <p className="text-foreground font-semibold">Silhouette = 0.458</p>
            </InfoCard>
            <InfoCard icon={ShieldCheck} title="Behaviour Detection">
              <p className="text-foreground font-semibold">6,397 customer-months flagged by Isolation Forest</p>
            </InfoCard>
            <InfoCard icon={Database} title="Risk Snapshot Consistency">
              <p className="text-foreground font-semibold">0 of 2,263 multi-dated customers changed raw risk level or capacity</p>
            </InfoCard>
            <InfoCard icon={Target} title="Goal Planning">
              <p className="text-foreground font-semibold">10,000 simulations per goal analysis</p>
            </InfoCard>
          </div>
          <TechnicalDetails title="View detailed evaluation">
            <DataTable
              caption="Summary of compared and selected methods"
              head={["Component", "Compared", "Selected", "Evaluation"]}
              rows={[
                ["Risk", "Logistic Regression, Random Forest, XGBoost, MLP", "Random Forest", "Macro-F1, 5-fold stratified CV"],
                ["Expense", "K-Means, GMM, Ward", "K-Means, k = 2", "Silhouette (GMM also BIC)"],
                ["Behaviour", "Rolling z-score, CUSUM, Isolation Forest", "All three, side by side", "Alert / flag counts"],
                ["Market", "Naive, ARIMA, LSTM, GRU; GARCH for volatility", "No model beat the naive baseline", "Walk-forward validation, Diebold-Mariano tests"],
                ["Goals", "—", "Monte Carlo", "Estimated success probability"],
                ["Portfolio", "Risk-based, MVO, HRP, 1/N", "By risk category", "Expected return, volatility, Sharpe; historical backtest"],
              ]}
            />
          </TechnicalDetails>
        </AboutSection>

        {/* 19. Integrity */}
        <AboutSection
          id="integrity"
          number={n("integrity")}
          title="Data Integrity"
          intro="How do we prevent data leakage?"
        >
          <p className="text-muted-foreground max-w-3xl">Training must never use information from the future.</p>
          <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
            <div className="bg-card rounded-lg border px-4 py-3 text-center">
              <p className="font-medium">Past data</p>
              <p className="text-muted-foreground text-xs">Training</p>
            </div>
            <ArrowRight className="text-muted-foreground size-4" aria-hidden="true" />
            <div className="rounded-lg border border-dashed px-3 py-2 text-center">
              <p className="text-muted-foreground text-xs">embargo gap</p>
            </div>
            <ArrowRight className="text-muted-foreground size-4" aria-hidden="true" />
            <div className="bg-card rounded-lg border px-4 py-3 text-center">
              <p className="font-medium">Future data</p>
              <p className="text-muted-foreground text-xs">Testing</p>
            </div>
          </div>
          <p className="text-muted-foreground max-w-3xl">
            An earlier leakage problem was found and fixed. The current pipeline uses point-in-time features and
            automated regression tests.
          </p>
          <TechnicalDetails title="View validation details">
            <List
              items={[
                "Before the fix, 76.5% of labelled customers' transaction-derived features and 99.95% of their market-derived features used information from after the customer's own label date; features are now computed point-in-time (with an as-of join for volatility and drawdown).",
                "Preprocessors are fitted on training data only and saved with each model.",
                "Market models use expanding-window walk-forward validation with an embargo gap — never a shuffled split on time-series data (504 initial training days, 5-day embargo, 63-day test windows, 10 windows per instrument).",
                "Behaviour baselines use strictly prior months; the current month is excluded from its own baseline (minimum 3 prior months).",
                "Market regime thresholds are derived from each training window only.",
                "Demo data is marked training_eligible = false and excluded from training.",
                "FAR-Trans and Kaggle populations are never artificially linked.",
                "random_state = 42 in every stochastic step.",
              ]}
            />
          </TechnicalDetails>
        </AboutSection>

        {/* 20. Limitations */}
        <AboutSection id="limitations" number={n("limitations")} title="Limitations">
          <List
            items={[
              "Market analysis uses historical data; it is not a future forecast.",
              "FAR-Trans represents a research population, not a deployment population.",
              "The Kaggle dataset is synthetic and is not linked to FAR-Trans.",
              "Risk-model performance is modest.",
              "The questionnaire contains questions/options, not customer answers.",
              "AutoGen is not part of the live analysis.",
              "The portfolio uses a three-asset universe.",
              "Individual debt, cash flow and net position are not recorded.",
              "The prototype does not execute trades or transfer money.",
            ]}
          />
        </AboutSection>

        {/* 21. Technical summary */}
        <AboutSection id="technical-summary" number={n("technical-summary")} title="Technical Summary & References">
          <div className="grid gap-4 md:grid-cols-2">
            <TechnicalDetails
              title="Dataset summary"
              items={[
                { label: "FAR-Trans", value: "29,090 customers; 388,048 transactions; 807 priced ISINs" },
                { label: "Risk training population", value: "21,528 customers, 4 genuine labels" },
                { label: "Kaggle (synthetic)", value: "32,424 rows, expense segmentation only" },
                { label: "Market data", value: "yfinance, 5 instruments, Jan 2022 – Sep 2026" },
              ]}
            />
            <TechnicalDetails
              title="Model summary"
              items={[
                { label: "Risk", value: "Random Forest, 300 trees, 20 features, macro-F1 0.4075 ± 0.0048" },
                { label: "Expense", value: "K-Means k = 2 on 4 income-normalised ratios, silhouette 0.458" },
                { label: "Behaviour", value: "z-score (threshold 2.0, 12-month window), CUSUM (k 0.5, h 5.0), Isolation Forest (5%)" },
                { label: "Market", value: "Naive / ARIMA / LSTM / GRU / GARCH; 15 DM tests, all p > 0.05" },
                { label: "Goals", value: "Bootstrap Monte Carlo, 10,000 paths, seed 42" },
                { label: "Explainability", value: "SHAP TreeExplainer computed offline for the risk model (1,000-row sample)" },
              ]}
            />
            <TechnicalDetails
              title="Validation strategy"
              items={[
                { label: "Risk", value: "5-fold stratified CV over customers, balanced class weights, point-in-time features" },
                { label: "Market", value: "Expanding-window walk-forward with a 5-day embargo" },
                { label: "Behaviour", value: "Strictly prior-month baselines (minimum 3 prior months)" },
              ]}
            />
            <TechnicalDetails
              title="Project references"
              items={[
                { label: "Metrics", value: "models/metrics.json" },
                { label: "Data quality", value: "reports/phase2_data_quality_report.md" },
                { label: "Leakage audit", value: "reports/phase3_leakage_audit.md" },
                { label: "Model reports", value: "reports/phase4–phase9 reports" },
                { label: "Decisions", value: "docs/DECISIONS.md (e.g. ADR-010: FAR-Trans and Kaggle never linked)" },
              ]}
            />
          </div>
        </AboutSection>
      </main>
      <HomeFooter />
    </div>
  )
}
