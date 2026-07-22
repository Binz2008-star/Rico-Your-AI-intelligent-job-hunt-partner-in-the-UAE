/**
 * EditorialInk — hand-authored SVG spot illustrations in the prospectus
 * identity: thin ink line work in currentColor, one hot red accent
 * (#C6492E), transparent background so the same drawing sits on the paper
 * atelier surfaces and the dark app pages alike.
 *
 * Every stroke carries data-draw + pathLength=100, which the global
 * `.ink-draw` rules (globals.css) turn into a staggered pen draw-in; red
 * accents carry data-accent and fade in after their lines land. Reduced
 * motion renders everything instantly. Stagger order comes from --d
 * (delay in ms) set inline per element.
 */

const RED = "#C6492E";

type InkProps = { className?: string; accent?: string };

function inkSvg(viewW: number, viewH: number) {
    return {
        viewBox: `0 0 ${viewW} ${viewH}`,
        fill: "none",
        stroke: "currentColor",
        strokeWidth: 1.6,
        strokeLinecap: "round" as const,
        strokeLinejoin: "round" as const,
        "aria-hidden": true,
    };
}

const draw = (d: number) => ({ "data-draw": true, pathLength: 100, style: { ["--d" as string]: d } });
const accent = (d: number) => ({ "data-accent": true, style: { ["--d" as string]: d } });

/** Jobs empty state — a magnifying glass resting on a small stack of listings. */
export function EmptyJobsInk({ className, accent: accentColor = RED }: InkProps) {
    return (
        <svg {...inkSvg(120, 120)} className={`ink-draw ${className ?? ""}`}>
            {/* paper stack */}
            <path {...draw(0)} d="M28 92 L24 40 a3 3 0 0 1 3-3 l52 0 a3 3 0 0 1 3 3 l-2 26" opacity={0.45} />
            <rect {...draw(120)} x="30" y="44" width="56" height="52" rx="3" />
            {/* listing lines */}
            <path {...draw(320)} d="M38 56 h28" opacity={0.7} />
            <path {...draw(400)} d="M38 64 h36" opacity={0.5} />
            <path {...draw(480)} d="M38 72 h24" opacity={0.5} />
            <path {...draw(560)} d="M38 86 h18" opacity={0.4} />
            {/* red seal on the listing */}
            <circle {...accent(1050)} cx="74" cy="84" r="6" stroke={accentColor} strokeWidth={1.6} />
            <circle {...accent(1150)} cx="74" cy="84" r="1.6" fill={accentColor} stroke="none" />
            {/* magnifying glass */}
            <circle {...draw(650)} cx="72" cy="48" r="17" strokeWidth={2} />
            <circle {...draw(750)} cx="72" cy="48" r="12.5" opacity={0.35} />
            <path {...draw(850)} d="M84.5 60.5 L98 74" strokeWidth={3.2} />
            <path {...draw(950)} d="M64 42 a9 9 0 0 1 6-3" opacity={0.5} />
        </svg>
    );
}

/** Applications empty state — a dossier tied with string, envelopes tucked in. */
export function EmptyApplicationsInk({ className, accent: accentColor = RED }: InkProps) {
    return (
        <svg {...inkSvg(120, 120)} className={`ink-draw ${className ?? ""}`}>
            {/* folder */}
            <path {...draw(0)} d="M24 46 v40 a4 4 0 0 0 4 4 h58 a4 4 0 0 0 4-4 V52 a4 4 0 0 0-4-4 H58 l-6-8 H28 a4 4 0 0 0-4 4 z" />
            <path {...draw(200)} d="M24 58 h66" opacity={0.4} />
            {/* envelopes peeking out */}
            <path {...draw(340)} d="M40 48 v-12 a2 2 0 0 1 2-2 h26 a2 2 0 0 1 2 2 v12" opacity={0.7} />
            <path {...draw(440)} d="M40 37 l15 9 15-9" opacity={0.55} />
            {/* string wrap */}
            <path {...draw(560)} d="M57 90 C50 76 64 66 57 48" opacity={0.6} />
            {/* wax seal */}
            <circle {...accent(950)} cx="57" cy="70" r="7.5" stroke={accentColor} strokeWidth={1.6} />
            <circle {...accent(1050)} cx="57" cy="70" r="3" stroke={accentColor} strokeWidth={1.2} />
        </svg>
    );
}

/** No-results empty state — an open field notebook, pen resting across it. */
export function EmptySearchInk({ className, accent: accentColor = RED }: InkProps) {
    return (
        <svg {...inkSvg(120, 120)} className={`ink-draw ${className ?? ""}`}>
            {/* open notebook */}
            <path {...draw(0)} d="M60 40 C48 34 32 34 24 38 v44 c8-4 24-4 36 2 12-6 28-6 36-2 V38 c-8-4-24-4-36 2 z" />
            <path {...draw(220)} d="M60 40 v46" opacity={0.5} />
            {/* ruled lines, left page */}
            <path {...draw(380)} d="M32 48 c8-2 16-2 22 0" opacity={0.4} />
            <path {...draw(450)} d="M32 56 c8-2 16-2 22 0" opacity={0.4} />
            <path {...draw(520)} d="M32 64 c8-2 16-2 22 0" opacity={0.4} />
            {/* right page stays blank — the "no results yet" page */}
            {/* pen across */}
            <path {...draw(650)} d="M50 88 L88 54" strokeWidth={2.4} />
            <path {...draw(780)} d="M88 54 l6-5 3 3 -5 6 z" />
            <path {...draw(880)} d="M50 88 l-5 4" opacity={0.6} />
            {/* red ribbon from the spine */}
            <path {...accent(1000)} d="M60 86 c0 6 -2 10 -5 14 l4-2 3 4" stroke={accentColor} strokeWidth={1.8} fill="none" />
        </svg>
    );
}

/** Blog cover — ATS guide: a CV sheet read through an optical lens. */
export function BlogCoverAtsInk({ className, accent: accentColor = RED }: InkProps) {
    return (
        <svg {...inkSvg(180, 120)} className={`ink-draw ${className ?? ""}`}>
            {/* CV sheet */}
            <rect {...draw(0)} x="36" y="18" width="58" height="84" rx="3" />
            <path {...draw(200)} d="M46 32 h20" strokeWidth={2.2} />
            <path {...draw(280)} d="M46 40 h14" opacity={0.5} />
            <path {...draw(360)} d="M46 52 h38" opacity={0.5} />
            <path {...draw(430)} d="M46 60 h38" opacity={0.5} />
            <path {...draw(500)} d="M46 68 h28" opacity={0.5} />
            <path {...draw(570)} d="M46 80 h38" opacity={0.5} />
            <path {...draw(640)} d="M46 88 h22" opacity={0.5} />
            {/* lens over the right edge, revealing structure */}
            <circle {...draw(720)} cx="108" cy="58" r="26" strokeWidth={2} />
            <path {...draw(840)} d="M96 50 h24 M96 58 h24 M96 66 h16" opacity={0.8} />
            <path {...draw(960)} d="M126 76 L142 92" strokeWidth={3} />
            {/* red approval seal */}
            <circle {...accent(1150)} cx="46" cy="97" r="6" stroke={accentColor} strokeWidth={1.6} />
            <path {...accent(1250)} d="M43.5 97 l2 2 3.5-4" stroke={accentColor} strokeWidth={1.4} />
        </svg>
    );
}

/** Blog cover — Dubai 2026: the skyline, a compass, one red sun. */
export function BlogCoverDubaiInk({ className, accent: accentColor = RED }: InkProps) {
    return (
        <svg {...inkSvg(180, 120)} className={`ink-draw ${className ?? ""}`}>
            {/* ground line */}
            <path {...draw(0)} d="M14 96 h152" opacity={0.5} />
            {/* Burj Khalifa */}
            <path {...draw(160)} d="M86 96 V44 l4-8 4 8 v52" />
            <path {...draw(320)} d="M90 24 v12 M90 36 l-3 6 M90 36 l3 6" />
            <path {...draw(430)} d="M82 96 V60 l4-4 M98 96 V60 l-4-4" opacity={0.7} />
            {/* neighbouring towers */}
            <path {...draw(560)} d="M56 96 V70 h12 v26" opacity={0.75} />
            <path {...draw(650)} d="M60 74 h4 M60 80 h4 M60 86 h4" opacity={0.4} />
            <path {...draw(720)} d="M112 96 V64 l8-6 8 6 v32" opacity={0.75} />
            <path {...draw(810)} d="M116 72 h8 M116 80 h8 M116 88 h8" opacity={0.4} />
            <path {...draw(880)} d="M38 96 V80 h10 v16" opacity={0.6} />
            <path {...draw(940)} d="M136 96 V78 h9 v18" opacity={0.6} />
            {/* red sun low beside the towers */}
            <circle {...accent(1100)} cx="30" cy="52" r="9" fill={accentColor} stroke="none" opacity={0.9} />
            {/* pocket compass */}
            <circle {...draw(1000)} cx="156" cy="88" r="8" />
            <path {...draw(1080)} d="M156 83 l2.5 5 -2.5 5 -2.5-5 z" opacity={0.8} />
        </svg>
    );
}

/** Blog cover — interviews: two chairs in conversation across a small table. */
export function BlogCoverInterviewInk({ className, accent: accentColor = RED }: InkProps) {
    return (
        <svg {...inkSvg(180, 120)} className={`ink-draw ${className ?? ""}`}>
            {/* left chair, facing right */}
            <path {...draw(0)} d="M44 44 v28 h16" />
            <path {...draw(150)} d="M44 72 v22 M60 72 v22" opacity={0.8} />
            <path {...draw(260)} d="M44 48 h14" opacity={0.5} />
            {/* right chair, facing left */}
            <path {...draw(380)} d="M136 44 v28 h-16" />
            <path {...draw(530)} d="M136 72 v22 M120 72 v22" opacity={0.8} />
            <path {...draw(620)} d="M136 48 h-14" opacity={0.5} />
            {/* table with carafe and glasses */}
            <path {...draw(700)} d="M76 70 h28 M90 70 v24 M82 94 h16" />
            <path {...draw(830)} d="M86 70 v-10 a4 4 0 0 1 8 0 v10" opacity={0.8} />
            <path {...draw(920)} d="M79 70 v-6 h4 v6 M97 70 v-6 h4 v6" opacity={0.6} />
            {/* red pocket square on the interviewer's chair */}
            <path {...accent(1080)} d="M132 52 l4 4 -4 4 -4-4 z" fill={accentColor} stroke="none" opacity={0.95} />
        </svg>
    );
}

/** slug → cover component for the career-guide articles. */
export const BLOG_COVERS: Record<string, (p: InkProps) => JSX.Element> = {
    "ats-friendly-cv-uae": BlogCoverAtsInk,
    "find-job-dubai-uae-2026": BlogCoverDubaiInk,
    "uae-interview-questions-answers": BlogCoverInterviewInk,
};
