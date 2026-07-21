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
// Phase 2 of #1262: the view-jobs navigation card is retired — the jobs-board
// pointer is spoken inside the message text instead.
const AGENTIC_UI = {
    actions: [
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
    // /command loads GET /chat/sessions on mount and its result drives
    // setMessages. Left unmocked it 404s from the dev server and its late
    // catch → legacy-history fallback fired AFTER the test had sent its search,
    // clobbering the optimistic transcript back to the welcome state (no cards).
    // Mock it to an empty, deterministic result so mount takes the early-return
    // "no threads yet" branch and never resets messages sent later.
    await page.route(`${PROXY_API}/rico/chat/sessions`, (route) =>
        route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ sessions: [], total: 0 }),
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

// The mocked stream emits a `token` then a `done` event (mockCommand above), so
// the transcript renders twice and the structured action-card buttons remount
// when the `done` frame is applied. Waiting only for the `chat-actions-row`
// container let a test interact during that remount, detaching the button
// (element was detached from the DOM → 30s timeout). These helpers gate every
// interaction on the settled, final card state instead.
const JOB_MATCH_CARD_IDS = [
    "action-card-chat-continue",
    "action-card-open-drawer",
] as const;

/** Wait for the streamed job-match cards to reach their final rendered state.
 *  Gates on attachment + visibility of all three structured cards (not their
 *  text) so both EN and AR (translated labels) are covered; per-card text stays
 *  asserted by the individual tests. */
async function waitForJobMatchCards(page: Page) {
    await expect(page.getByTestId("chat-actions-row")).toBeVisible();
    // Streaming has fully settled once the caret is gone; after this the
    // transcript stops re-rendering, so the fade-in cards no longer remount
    // under a subsequent click (the detached-DOM race).
    await expect(page.getByTestId("transcript-streaming-caret")).toHaveCount(0);
    for (const id of JOB_MATCH_CARD_IDS) {
        await expect(page.getByTestId(id)).toBeVisible();
    }
}

/** Re-resolve a streamed card and confirm it is attached, visible and enabled
 *  immediately before clicking — the post-`done` remount can invalidate a
 *  handle captured earlier, so the click must act on a freshly resolved,
 *  settled element. */
async function clickSettledCard(page: Page, testId: string) {
    const card = page.getByTestId(testId);
    await expect(card).toBeVisible();
    await expect(card).toBeEnabled();
    await card.click();
}

async function searchAndOpenCards(
    page: Page,
    query: string,
    chatBodies: Array<Record<string, unknown>>,
) {
    const input = page.getByTestId("atelier-composer").locator("textarea");
    const send = page.getByTestId("send-button");
    await expect(input).toBeVisible();
    // Hydration guard: /command's textarea is a controlled React input, so a
    // fill/submit issued before hydration is silently discarded — React takes
    // over the textarea, the value is lost, Send stays disabled, and nothing is
    // sent (the test then saw the welcome state with no cards). Retry the
    // fill+submit until the request has actually registered (`chatBodies` grew),
    // and skip the action entirely once it has, so the tests' exact request-count
    // assertions still hold (no double-send). `send.click()` is used instead of a
    // keyboard Enter because it drives the same onSend the product uses without a
    // keypress race. Condition-based retry with a bounded local budget — not a
    // fixed sleep and not a global-timeout bump.
    await expect(async () => {
        if (chatBodies.length === 0) {
            await input.fill(query);
            await expect(send).toBeEnabled({ timeout: 1000 });
            await send.click();
        }
        await expect.poll(() => chatBodies.length, { timeout: 2000 }).toBeGreaterThan(0);
    }).toPass({ timeout: 20000 });
    // Settle gate: the full, final card set must be rendered before any test
    // interacts with a card (removes the streamed re-render race).
    await waitForJobMatchCards(page);
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
        await searchAndOpenCards(page, "Find me Senior HSE Manager jobs in Dubai", chatBodies);
        expect(chatBodies).toHaveLength(1);

        // The cards render; refine is the structured open_drawer one.
        // (Phase 2 of #1262: no navigation card — the jobs-board pointer is
        // spoken in the message text.)
        await expect(page.getByTestId("action-card-chat-continue")).toHaveText("Save search");
        const refine = page.getByTestId("action-card-open-drawer");
        await expect(refine).toHaveText("Refine search");
        await shot(page, "1-en-cards");

        // Click refine: panel opens, NO chat request fires, no "Refine search"
        // user bubble ever appears in the transcript.
        await clickSettledCard(page, "action-card-open-drawer");
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
        // The composed query renders as a normal user turn. Scope to the user
        // transcript row that contains it: RicoUserBubble nests the text in two
        // elements that each exact-match, so an unscoped exact getByText hits a
        // 2-element strict violation. This asserts the same product fact — the
        // composed query is displayed to the user — against the semantic row.
        await expect(
            page
                .getByTestId("transcript-you-row")
                .filter({ hasText: "Find Senior HSE Manager jobs in Abu Dhabi" }),
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
        await searchAndOpenCards(page, "Find me Senior HSE Manager jobs in Dubai", chatBodies);

        await clickSettledCard(page, "action-card-chat-continue");
        await expect.poll(() => chatBodies.length).toBe(2);
        expect(chatBodies[1].message).toBe("save this search for Senior HSE Manager");
        expect(chatBodies[1].message).not.toBe("Save search");
        await shot(page, "4-en-save-search-payload");
    });

    test("AR: panel is bilingual and composes an Arabic query", async ({ page }) => {
        const chatBodies = await mockCommand(page);
        await page.addInitScript(() => localStorage.setItem("rico-language", "ar"));
        await page.goto("/command");
        await searchAndOpenCards(page, "ابحث عن وظائف مدير سلامة في دبي", chatBodies);

        await clickSettledCard(page, "action-card-open-drawer");
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
