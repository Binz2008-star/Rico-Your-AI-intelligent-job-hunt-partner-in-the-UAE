"use client";

import { RicoMessageBubble } from "@/components/ui/rico/RicoMessageBubble";
import { RicoJobMatchCard, JobMatchData } from "@/components/ui/rico/RicoJobMatchCard";

export default function CommandPrimitivesSandbox() {
  const handleActionClick = (action: string, job: JobMatchData) => {
    console.log("Action clicked:", action, "for job:", job.title);
  };

  const sampleJobMatch: JobMatchData = {
    title: "Senior Software Engineer",
    company: "TechCorp Inc.",
    location: "San Francisco, CA",
    score: 0.85,
    confidence: "high",
    match_reasons: [
      "Your experience with React and TypeScript aligns perfectly",
      "Previous role at similar scale company",
      "Strong backend experience with Node.js",
      "Leadership experience matches senior requirements",
    ],
    match_concerns: [
      "Role requires more cloud infrastructure experience",
      "Compensation may be below market rate",
    ],
    missing_facts: ["Salary range", "Remote policy", "Team size"],
    recommended_action: "Apply now and ask about compensation during first interview",
    actions: ["Apply now", "Save for later", "View details"],
  };

  const longJobMatch: JobMatchData = {
    title: "Very Long Job Title That Might Truncate On Smaller Screens And Mobile Devices With Limited Space",
    company: "Extremely Long Company Name That Goes On And On Without Stopping",
    location: "San Francisco, California, United States of America",
    score: 0.72,
    confidence: "medium",
    match_reasons: ["Good fit for skills"],
    match_concerns: [],
    missing_facts: [],
    recommended_action: "Consider applying",
    actions: ["Apply"],
  };

  const emptyJobMatch: JobMatchData = {
    title: "Minimal Job",
    company: "Simple Co",
    score: 0.5,
    confidence: "low",
  };

  return (
    <div className="min-h-screen bg-[var(--rico-bg)] p-8">
      <div className="max-w-4xl mx-auto space-y-12">
        <h1 className="text-3xl font-bold text-[var(--rico-fg-1)]">Command Primitives Sandbox</h1>
        <p className="text-[var(--rico-fg-3)]">Visual testing for RicoMessageBubble and RicoJobMatchCard</p>

        {/* RicoMessageBubble Tests */}
        <section className="space-y-6">
          <h2 className="text-xl font-semibold text-[var(--rico-fg-1)]">RicoMessageBubble</h2>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">User variant (short)</h3>
            <RicoMessageBubble variant="user">Hello, I need help with my career.</RicoMessageBubble>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">User variant (long)</h3>
            <RicoMessageBubble variant="user">
              I have been working in software engineering for the past 5 years, primarily focusing on frontend development with React and TypeScript. I am looking to transition into a more senior role that would allow me to take on more leadership responsibilities while still being hands-on with code. I am particularly interested in companies that value work-life balance and have a strong engineering culture.
            </RicoMessageBubble>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Assistant variant (short, no glass)</h3>
            <RicoMessageBubble variant="assistant">I can help with that. What is your current role?</RicoMessageBubble>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Assistant variant (long, no glass)</h3>
            <RicoMessageBubble variant="assistant">
              Based on your profile, I can see you have strong experience in frontend development. Your skills in React and TypeScript are highly valued in the current market. I recommend focusing on roles that offer growth opportunities in both technical depth and leadership. Companies like Stripe, Vercel, and Linear might be good targets for your next move.
            </RicoMessageBubble>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Assistant variant (long, with glass wrap)</h3>
            <RicoMessageBubble variant="assistant" useGlassWrap>
              Based on your profile, I can see you have strong experience in frontend development. Your skills in React and TypeScript are highly valued in the current market. I recommend focusing on roles that offer growth opportunities in both technical depth and leadership. Companies like Stripe, Vercel, and Linear might be good targets for your next move.
            </RicoMessageBubble>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">System variant</h3>
            <RicoMessageBubble variant="system">Session expired. Please sign in again.</RicoMessageBubble>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Error variant</h3>
            <RicoMessageBubble variant="error">Could not reach Rico. Check your connection.</RicoMessageBubble>
          </div>
        </section>

        {/* RicoJobMatchCard Tests */}
        <section className="space-y-6">
          <h2 className="text-xl font-semibold text-[var(--rico-fg-1)]">RicoJobMatchCard</h2>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Full card with all sections</h3>
            <RicoJobMatchCard match={sampleJobMatch} onActionClick={handleActionClick} />
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Long company/title names (truncation test)</h3>
            <RicoJobMatchCard match={longJobMatch} onActionClick={handleActionClick} />
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Minimal card (empty optional sections)</h3>
            <RicoJobMatchCard match={emptyJobMatch} onActionClick={handleActionClick} />
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Score 0.92 (0-1 range, should be Strong match/cyan)</h3>
            <RicoJobMatchCard
              match={{ ...sampleJobMatch, score: 0.92, confidence: "high" }}
              onActionClick={handleActionClick}
            />
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Score 92 (0-100 range, should be Strong match/cyan)</h3>
            <RicoJobMatchCard
              match={{ ...sampleJobMatch, score: 92, confidence: "high" }}
              onActionClick={handleActionClick}
            />
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Score 50 (0-100 range, should be Possible match/magenta)</h3>
            <RicoJobMatchCard
              match={{ ...sampleJobMatch, score: 50, confidence: "low" }}
              onActionClick={handleActionClick}
            />
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Score 0.65 (0-1 range, should be Good match/default)</h3>
            <RicoJobMatchCard
              match={{ ...sampleJobMatch, score: 0.65, confidence: "medium" }}
              onActionClick={handleActionClick}
            />
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-medium text-[var(--rico-fg-2)]">Score 0.4 (0-1 range, should be Possible match/magenta)</h3>
            <RicoJobMatchCard
              match={{ ...sampleJobMatch, score: 0.4, confidence: "low" }}
              onActionClick={handleActionClick}
            />
          </div>
        </section>

        {/* Mobile width test */}
        <section className="space-y-6">
          <h2 className="text-xl font-semibold text-[var(--rico-fg-1)]">Mobile Width Test (~360px)</h2>
          <div className="w-[360px] mx-auto space-y-4 border border-[var(--rico-border-soft)] p-4 rounded-lg">
            <RicoJobMatchCard match={sampleJobMatch} onActionClick={handleActionClick} />
          </div>
        </section>
      </div>
    </div>
  );
}
