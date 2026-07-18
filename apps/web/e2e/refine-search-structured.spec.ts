import { expect, test, type Page } from "@playwright/test";

/**
 * refine-search-structured.spec.ts — P1 smoke (2026-07-19).
 *
 * The "Refine search" card is a STRUCTURED open_drawer action: clicking it
 * must never send any chat message; the refinement panel collects role+city
 * and only the final composed natural-language query reaches the chat
 * endpoint. Also pins the prompt→message contract repair for "Save search".
 *
 * The job_matches agentic_ui fixture below is the REAL output of
 * src/services/agentic_ui_composer.compose() for this response type — keep
 * them in sync (tests/test_agentic_ui_composer.py pins the backend side).
 */

const PROXY_API = "/proxy/api/v1";

// Real composer output for {type: job_matches, matches:[…], search_query: "Senior HSE Manager"}
const AGENTIC_UI = {
    actions: [
        {
            id: "view-jobs",
            label: "View all jobs",
            kind: "navigate",
            impact: "low",
            requires_confirmation: false,
            href: "/flow",
            payload: {},
        },
        {
            id: "save-search",
            label: "Save search",
            kind: "chat_continue",
            impact: "medium",
            requires_confirmation: false,
            payload: { message: "save this search for Senior HSE Manager" },
        },
        {
            id: "refine-search",
            label: "Refine search",
            kind: "open_drawer",
            impact: "low",
            requires_confirmation: false,
            payload: { drawer: "refine_search", search_query: "Senior HSE Manager" },
        },
    ],
    progress: [],
    proposed_changes: [],
    attachment_analysis: [],
};

const JOB_MATCHES_RESPONSE = {
    response: "Found 2 Senior HSE Manager roles in Dubai:",
    type: "job_matches",
    search_query: "Senior HSE Manager",
    matches: [
        {
            title: "Senior HSE Manager",
            company: "ACME Gulf",
            location: "Dubai, AE",
            link: "https://jobs.example.com/1",
            apply_link: "https://jobs.example.com/1",
            score: 90,
        },
        {
            title: "Senior HSE Leader",
            company: "Falcon Industrial",
            location: "Dubai, AE",
            link: "https://jobs.example.com/2",
            apply_link: "https://jobs.example.com/2",
            score: 85,
        },
    ],
    agentic_ui: AGENTIC_UI,
    messages_remaining: 9,
};

/** Mount auth + history + stream mocks; returns the captured chat bodies. */
async function mockCommand(page: Page): Promise<Array<Record<string, unknown>>> {
    const chatBodies: Array<Record<string, unknown>> = [];

    await page.route(`${PROXY_API}/me`, (route) =>
        route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ email: "smoke@example.com", role: "user", authenticated: true }),
        }),
    );
    await page.route(`${PROXY_API}/rico/chat/history**`, (route) =>
        route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ messages: [], total: 0, has_more: false }),
        }),
    );
    await page.route(`${PROXY_API}/rico/chat/stream`, async (route) => {
        const body = route.request().postDataJSON() as Record<string, unknown>;
        chatBodies.push(body);
        // First message gets the job-matches card set; later ones a plain ack.
        const payload = chatBodies.length === 1
            ? JOB_MATCHES_RESPONSE
            : { response: "Done.", type: "chat", messages_remaining: 8 };
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body:
                `data: ${JSON.stringify({ type: "token", text: payload.response })}\n\n` +
                `data: ${JSON.stringify({ type: "done", response: payload })}\n\n`,
        });
    });

    return chatBodies;
}

async function searchAndOpenCards(page: Page, query: string) {
    const input = page.getByTestId("atelier-composer").locator("textarea");
    await input.fill(query);
    await input.press("Enter");
    await expect(page.getByTestId("chat-actions-row")).toBeVisible();
}

function shot(page: Page, name: string) {
    const dir = process.env.SMOKE_SHOT_DIR;
    if (!dir) return Promise.resolve(Buffer.from(""));
    return page.screenshot({ path: `${dir}/${name}.png`, fullPage: false });
}

test.describe("Refine search — structured action (P1)", () => {
    test("EN: refine opens panel with ZERO chat traffic; only the composed query is sent", async ({ page }) => {
        const chatBodies = await mockCommand(page);
        await page.goto("/command");
        await searchAndOpenCards(page, "Find me Senior HSE Manager jobs in Dubai");
        expect(chatBodies).toHaveLength(1);

        // The three cards render; refine is the structured open_drawer one.
        await expect(page.getByTestId("action-card-navigate")).toHaveText("View all jobs");
        await expect(page.getByTestId("action-card-chat-continue")).toHaveText("Save search");
        const refine = page.getByTestId("action-card-open-drawer");
        await expect(refine).toHaveText("Refine search");
        await shot(page, "1-en-cards");

        // Click refine: panel opens, NO chat request fires, no "Refine search"
        // user bubble ever appears in the transcript.
        await refine.click();
        await expect(page.getByTestId("refine-search-panel")).toBeVisible();
        expect(chatBodies).toHaveLength(1); // unchanged — nothing was sent
        await expect(page.getByTestId("refine-role-input")).toHaveValue("Senior HSE Manager");
        await shot(page, "2-en-panel-open");

        // City + submit → exactly one new request whose message is the
        // composed natural query; the panel closes.
        await page.getByTestId("refine-city-abu-dhabi").click();
        await page.getByTestId("refine-submit").click();
        await expect(page.getByTestId("refine-search-panel")).toBeHidden();
        await expect.poll(() => chatBodies.length).toBe(2);
        expect(chatBodies[1].message).toBe("Find Senior HSE Manager jobs in Abu Dhabi");
        await expect(
            page.getByText("Find Senior HSE Manager jobs in Abu Dhabi", { exact: true }),
        ).toBeVisible();
        await shot(page, "3-en-composed-query-sent");

        // Global pin: no request ever carried UI wording.
        for (const body of chatBodies) {
            expect(String(body.message).toLowerCase()).not.toContain("refine");
        }
    });

    test("EN: Save search sends its payload message, never the label", async ({ page }) => {
        const chatBodies = await mockCommand(page);
        await page.goto("/command");
        await searchAndOpenCards(page, "Find me Senior HSE Manager jobs in Dubai");

        await page.getByTestId("action-card-chat-continue").click();
        await expect.poll(() => chatBodies.length).toBe(2);
        expect(chatBodies[1].message).toBe("save this search for Senior HSE Manager");
        expect(chatBodies[1].message).not.toBe("Save search");
        await shot(page, "4-en-save-search-payload");
    });

    test("AR: panel is bilingual and composes an Arabic query", async ({ page }) => {
        const chatBodies = await mockCommand(page);
        await page.addInitScript(() => localStorage.setItem("rico-language", "ar"));
        await page.goto("/command");
        await searchAndOpenCards(page, "ابحث عن وظائف مدير سلامة في دبي");

        await page.getByTestId("action-card-open-drawer").click();
        const panel = page.getByTestId("refine-search-panel");
        await expect(panel).toBeVisible();
        await expect(panel).toContainText("حسّن بحثك");
        await shot(page, "5-ar-panel-open");

        const role = page.getByTestId("refine-role-input");
        await role.fill("مدير سلامة");
        await page.getByTestId("refine-city-dubai").click();
        await page.getByTestId("refine-submit").click();
        await expect.poll(() => chatBodies.length).toBe(2);
        expect(chatBodies[1].message).toBe("ابحث عن وظائف مدير سلامة في دبي");
        await shot(page, "6-ar-composed-query-sent");
    });
});
