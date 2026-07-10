import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders as render } from "./test-utils";
import { JobCard } from "@/components/jobs/JobCard";
import type { Job } from "@/types";

describe("JobCard match explanation", () => {
    it("renders the structured explanation sections", () => {
        const job: Job = {
            job_id: "job-1",
            title: "Senior Python Developer",
            company: "Acme",
            location: "Remote",
            score: 84,
            reason: "",
            apply_url: "https://example.com/jobs/1",
            tags: ["Python"],
            match_explanation: {
                verdict: "strong_fit",
                summary: "Strong fit for Senior Python Developer at Acme based on the current profile overlap and score.",
                why_this_fits: ["Matches your skills: Python, SQL.", "Match score is 84%."],
                worth_checking: ["Salary is not listed."],
                recommended_next_step: "Apply or ask Rico to tailor your CV for this role.",
                confidence: "high",
            },
        };

        render(<JobCard job={job} />);

        expect(screen.getByText("Strong fit")).toBeInTheDocument();
        expect(screen.getByText("Why Rico likes this")).toBeInTheDocument();
        expect(screen.getByText("Worth checking")).toBeInTheDocument();
        expect(screen.getByText("Recommended next step")).toBeInTheDocument();
        expect(screen.getByText("Matches your skills: Python, SQL.")).toBeInTheDocument();
        expect(screen.getByText("Salary is not listed.")).toBeInTheDocument();
        expect(screen.getByText("Apply or ask Rico to tailor your CV for this role.")).toBeInTheDocument();
    });
});
