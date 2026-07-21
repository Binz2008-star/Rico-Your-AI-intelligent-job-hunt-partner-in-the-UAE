// Static bilingual career-guide content for the public /blog section.
// Pure data module (no React) so it can be imported from both server
// components (metadata, JSON-LD, sitemap) and client components (rendering).
//
// Adding a post: append to POSTS below — the index page, the per-post route
// (generateStaticParams), and sitemap.ts all derive from this array.

export interface LocalizedText {
    en: string;
    ar: string;
}

export interface BlogSection {
    heading: LocalizedText;
    paragraphs: { en: string[]; ar: string[] };
    bullets?: { en: string[]; ar: string[] };
}

export interface BlogPost {
    slug: string;
    title: LocalizedText;
    description: LocalizedText;
    /** ISO date used for JSON-LD datePublished and sitemap lastmod. */
    datePublished: string;
    dateModified: string;
    readingMinutes: number;
    keywords: string[];
    intro: { en: string[]; ar: string[] };
    sections: BlogSection[];
}

export const POSTS: BlogPost[] = [
    {
        slug: "ats-friendly-cv-uae",
        title: {
            en: "How to Write an ATS-Friendly CV for the UAE (2026 Guide)",
            ar: "كيف تكتب سيرة ذاتية تجتاز أنظمة ATS في الإمارات (دليل 2026)",
        },
        description: {
            en: "Most CVs in the UAE are rejected by ATS software before a human reads them. Learn the format, keywords, and structure that get your CV past the filters and in front of recruiters in Dubai and Abu Dhabi.",
            ar: "معظم السير الذاتية في الإمارات تُرفض آلياً قبل أن يقرأها إنسان. تعلّم التنسيق والكلمات المفتاحية والهيكل الذي يجعل سيرتك تتجاوز الفلاتر وتصل إلى مسؤولي التوظيف في دبي وأبوظبي.",
        },
        datePublished: "2026-07-21",
        dateModified: "2026-07-21",
        readingMinutes: 7,
        keywords: [
            "ATS friendly CV UAE",
            "CV format Dubai",
            "resume ATS 2026",
            "CV writing UAE",
            "سيرة ذاتية الإمارات",
        ],
        intro: {
            en: [
                "In the UAE, most mid-size and large employers screen every CV with an Applicant Tracking System (ATS) before a recruiter ever opens it. If your CV is not machine-readable, it can be filtered out no matter how strong your experience is.",
                "This guide covers the exact formatting rules, keyword strategy, and UAE-specific details that help your CV pass ATS screening in Dubai, Abu Dhabi, and across the Emirates.",
            ],
            ar: [
                "في الإمارات، تقوم معظم الشركات المتوسطة والكبيرة بفرز كل سيرة ذاتية عبر نظام تتبع المتقدمين (ATS) قبل أن يفتحها أي مسؤول توظيف. إذا لم تكن سيرتك قابلة للقراءة آلياً، فقد تُستبعد مهما كانت خبرتك قوية.",
                "يغطي هذا الدليل قواعد التنسيق الدقيقة واستراتيجية الكلمات المفتاحية والتفاصيل الخاصة بسوق الإمارات التي تساعد سيرتك على اجتياز فرز ATS في دبي وأبوظبي وسائر الإمارات.",
            ],
        },
        sections: [
            {
                heading: {
                    en: "What an ATS actually does with your CV",
                    ar: "ماذا يفعل نظام ATS بسيرتك الذاتية فعلياً",
                },
                paragraphs: {
                    en: [
                        "An ATS parses your CV into structured fields — name, contact, work history, skills — then scores it against the job description. Recruiters typically review only the top-ranked profiles. Two things break this process: formatting the parser cannot read, and missing keywords the scoring engine expects.",
                    ],
                    ar: [
                        "يحوّل نظام ATS سيرتك الذاتية إلى حقول منظمة — الاسم، بيانات التواصل، الخبرات، المهارات — ثم يمنحها درجة مقارنةً بالوصف الوظيفي. عادةً لا يراجع مسؤولو التوظيف إلا الملفات الأعلى ترتيباً. شيئان يكسران هذه العملية: تنسيق لا يستطيع النظام قراءته، وكلمات مفتاحية ناقصة يتوقعها محرك التقييم.",
                    ],
                },
            },
            {
                heading: {
                    en: "Formatting rules that pass the parser",
                    ar: "قواعد التنسيق التي تجتاز القارئ الآلي",
                },
                paragraphs: {
                    en: [
                        "Keep the file simple and predictable. Decorative templates that look impressive to humans are the most common reason CVs fail parsing.",
                    ],
                    ar: [
                        "اجعل الملف بسيطاً ومتوقعاً. القوالب الزخرفية التي تبدو جذابة للبشر هي السبب الأكثر شيوعاً لفشل قراءة السير الذاتية آلياً.",
                    ],
                },
                bullets: {
                    en: [
                        "Use a single-column layout — tables, text boxes, and two-column designs scramble the parsing order.",
                        "Save as .docx or a text-based PDF (never a scanned image).",
                        "Use standard section headings: Work Experience, Education, Skills, Certifications.",
                        "Avoid headers/footers for contact details — some parsers skip them entirely.",
                        "Use standard fonts (Arial, Calibri) at 10–12pt; skip icons, charts, and photos of text.",
                    ],
                    ar: [
                        "استخدم تخطيطاً بعمود واحد — الجداول ومربعات النص والتصاميم ذات العمودين تُربك ترتيب القراءة.",
                        "احفظ الملف بصيغة .docx أو PDF نصّي (وليس صورة ممسوحة ضوئياً أبداً).",
                        "استخدم عناوين أقسام قياسية: الخبرة العملية، التعليم، المهارات، الشهادات.",
                        "تجنّب وضع بيانات التواصل في الترويسة أو التذييل — بعض الأنظمة تتجاهلها تماماً.",
                        "استخدم خطوطاً قياسية (Arial أو Calibri) بحجم 10–12، وتجنّب الأيقونات والرسوم وصور النصوص.",
                    ],
                },
            },
            {
                heading: {
                    en: "Keyword strategy: mirror the job description",
                    ar: "استراتيجية الكلمات المفتاحية: طابِق الوصف الوظيفي",
                },
                paragraphs: {
                    en: [
                        "ATS scoring is largely keyword matching. Read the job description and use its exact terminology — if the posting says \"accounts payable\", write \"accounts payable\", not just \"AP\". Include both the spelled-out form and the abbreviation for key terms (e.g. \"Customer Relationship Management (CRM)\").",
                        "Place your most important keywords in three locations: the professional summary at the top, the skills section, and inside actual work-experience bullet points. Keywords listed only in a skills section without supporting experience score lower on modern systems.",
                    ],
                    ar: [
                        "تقييم ATS يعتمد إلى حد كبير على مطابقة الكلمات المفتاحية. اقرأ الوصف الوظيفي واستخدم مصطلحاته الحرفية — إذا ذكر الإعلان \"حسابات الموردين\" فاكتبها كما هي. وأدرج الصيغة الكاملة والاختصار معاً للمصطلحات المهمة (مثل: \"إدارة علاقات العملاء (CRM)\").",
                        "ضع أهم كلماتك المفتاحية في ثلاثة مواضع: الملخص المهني في الأعلى، وقسم المهارات، وداخل نقاط الخبرة العملية الفعلية. الكلمات المذكورة في قسم المهارات فقط دون خبرة داعمة تحصل على درجة أقل في الأنظمة الحديثة.",
                    ],
                },
            },
            {
                heading: {
                    en: "UAE-specific CV details",
                    ar: "تفاصيل خاصة بالسيرة الذاتية في الإمارات",
                },
                paragraphs: {
                    en: [
                        "The UAE market has its own conventions that both ATS filters and recruiters expect to see.",
                    ],
                    ar: [
                        "لسوق الإمارات أعرافه الخاصة التي يتوقعها كل من فلاتر ATS ومسؤولي التوظيف.",
                    ],
                },
                bullets: {
                    en: [
                        "State your location and visa status clearly (e.g. \"Dubai, UAE — employment visa, transferable\" or \"on spouse/golden visa\"). Recruiters filter on this.",
                        "Include your nationality and languages — standard practice in the GCC, and many searches filter by language.",
                        "Mention your notice period; \"immediately available\" is a genuine ranking advantage in the UAE's fast hiring cycles.",
                        "Use a UAE mobile number (+971) if you have one — some recruiters filter out foreign numbers.",
                        "Keep it to two pages maximum; senior roles may stretch to three.",
                    ],
                    ar: [
                        "اذكر موقعك وحالة تأشيرتك بوضوح (مثل: \"دبي، الإمارات — تأشيرة عمل قابلة للتحويل\" أو \"تأشيرة ذهبية\"). مسؤولو التوظيف يفرزون بناءً على ذلك.",
                        "أدرج جنسيتك ولغاتك — ممارسة قياسية في دول الخليج، وكثير من عمليات البحث تُفلتر حسب اللغة.",
                        "اذكر فترة الإشعار؛ عبارة \"متاح فوراً\" ميزة حقيقية في دورات التوظيف السريعة بالإمارات.",
                        "استخدم رقم هاتف إماراتي (+971) إن وُجد — بعض المسؤولين يستبعدون الأرقام الأجنبية.",
                        "التزم بصفحتين كحد أقصى؛ وقد تمتد الأدوار القيادية إلى ثلاث.",
                    ],
                },
            },
            {
                heading: {
                    en: "Test your CV before you apply",
                    ar: "اختبر سيرتك قبل التقديم",
                },
                paragraphs: {
                    en: [
                        "Before sending applications, check how software actually reads your CV: copy-paste the file's text into a plain text editor — if the order is scrambled or sections are missing, an ATS will see the same mess.",
                        "Rico Hunt does this automatically: upload your CV and Rico analyses it against real UAE job descriptions, shows your match score per role, and suggests targeted edits — in English or Arabic. It's free to start at ricohunt.com.",
                    ],
                    ar: [
                        "قبل إرسال الطلبات، تحقق من كيفية قراءة البرمجيات لسيرتك فعلياً: انسخ نص الملف والصقه في محرر نصوص عادي — إذا كان الترتيب مبعثراً أو الأقسام ناقصة، فسيرى نظام ATS الفوضى نفسها.",
                        "يقوم ريكو هانت بذلك تلقائياً: ارفع سيرتك الذاتية وسيحللها ريكو مقارنةً بأوصاف وظائف حقيقية في الإمارات، ويعرض درجة تطابقك مع كل دور، ويقترح تعديلات محددة — بالعربية أو الإنجليزية. ابدأ مجاناً على ricohunt.com.",
                    ],
                },
            },
        ],
    },
    {
        slug: "find-job-dubai-uae-2026",
        title: {
            en: "How to Find a Job in Dubai and the UAE in 2026: Step-by-Step",
            ar: "كيف تجد وظيفة في دبي والإمارات في 2026: خطوة بخطوة",
        },
        description: {
            en: "A practical, up-to-date roadmap for landing a job in Dubai, Abu Dhabi, or anywhere in the UAE — visas, job boards, recruiters, timelines, and the mistakes that cost applicants months.",
            ar: "خارطة طريق عملية ومحدّثة للحصول على وظيفة في دبي أو أبوظبي أو أي مكان في الإمارات — التأشيرات ومواقع التوظيف وشركات التوظيف والجداول الزمنية والأخطاء التي تكلف المتقدمين شهوراً.",
        },
        datePublished: "2026-07-21",
        dateModified: "2026-07-21",
        readingMinutes: 8,
        keywords: [
            "find job Dubai 2026",
            "jobs in UAE",
            "Dubai job search guide",
            "UAE work visa job",
            "وظائف دبي",
            "البحث عن عمل في الإمارات",
        ],
        intro: {
            en: [
                "The UAE remains one of the most active hiring markets in the region — but it is also one of the most competitive, with hundreds of applicants per posting in popular fields. The difference between a three-month search and a twelve-month search is usually process, not luck.",
                "Here is the step-by-step approach that consistently works in the UAE market in 2026.",
            ],
            ar: [
                "لا تزال الإمارات واحدة من أنشط أسواق التوظيف في المنطقة — لكنها أيضاً من أكثرها تنافسية، إذ يتقدم مئات المرشحين لكل إعلان في المجالات المطلوبة. الفرق بين بحث يستغرق ثلاثة أشهر وآخر يستغرق اثني عشر شهراً هو المنهجية عادةً، لا الحظ.",
                "إليك المنهجية خطوة بخطوة التي تنجح باستمرار في سوق الإمارات في 2026.",
            ],
        },
        sections: [
            {
                heading: {
                    en: "Step 1 — Understand your visa position first",
                    ar: "الخطوة 1 — افهم وضع تأشيرتك أولاً",
                },
                paragraphs: {
                    en: [
                        "Employers sort candidates into \"inside the country and available\" versus \"needs relocation and sponsorship\". If you are already in the UAE on any valid visa (visit, spouse, golden, or a transferable employment visa), say so at the top of your CV — it materially increases response rates. If you are applying from abroad, target larger companies and free-zone employers that regularly sponsor international hires, and expect a longer timeline.",
                    ],
                    ar: [
                        "يصنّف أصحاب العمل المرشحين إلى \"داخل الدولة ومتاح\" مقابل \"يحتاج انتقالاً وكفالة\". إذا كنت في الإمارات بالفعل بأي تأشيرة سارية (زيارة، إقامة زوج/زوجة، ذهبية، أو تأشيرة عمل قابلة للتحويل)، فاذكر ذلك في أعلى سيرتك — فهو يرفع معدلات الرد بشكل ملموس. أما إن كنت تتقدم من الخارج، فاستهدف الشركات الكبرى وشركات المناطق الحرة التي تكفل الموظفين الدوليين بانتظام، وتوقّع مدة أطول.",
                    ],
                },
            },
            {
                heading: {
                    en: "Step 2 — Fix your CV and LinkedIn before applying anywhere",
                    ar: "الخطوة 2 — أصلح سيرتك الذاتية ولينكدإن قبل التقديم في أي مكان",
                },
                paragraphs: {
                    en: [
                        "Applying with a weak CV burns opportunities you cannot re-apply to for months. Make your CV ATS-friendly (see our dedicated guide), then align your LinkedIn headline and location to Dubai/UAE — recruiters in the Emirates source heavily from LinkedIn search, and your location field is a filter.",
                    ],
                    ar: [
                        "التقديم بسيرة ذاتية ضعيفة يحرق فرصاً لا يمكنك إعادة التقدم لها لشهور. اجعل سيرتك متوافقة مع أنظمة ATS (راجع دليلنا المخصص)، ثم اضبط عنوان ملفك على لينكدإن وموقعك ليكونا دبي/الإمارات — مسؤولو التوظيف في الإمارات يعتمدون بكثافة على بحث لينكدإن، وحقل الموقع لديك فلتر أساسي.",
                    ],
                },
            },
            {
                heading: {
                    en: "Step 3 — Cover every serious job channel",
                    ar: "الخطوة 3 — غطِّ كل قنوات التوظيف الجادة",
                },
                paragraphs: {
                    en: [
                        "No single job board covers the UAE market. A serious search runs across all of these in parallel:",
                    ],
                    ar: [
                        "لا يغطي أي موقع توظيف واحد سوق الإمارات كاملاً. البحث الجاد يجري عبر كل هذه القنوات بالتوازي:",
                    ],
                },
                bullets: {
                    en: [
                        "LinkedIn — the primary channel for professional roles; set alerts and apply within 24–48 hours of posting.",
                        "Bayt, Naukrigulf, GulfTalent — the regional boards where many local employers post first.",
                        "Indeed and Glassdoor — aggregate many UAE listings, including SMEs.",
                        "Company career pages — government entities, banks, airlines, and large groups often post only on their own sites.",
                        "Recruitment agencies (Hays, Michael Page, Robert Half, plus industry specialists) — essential for mid-senior roles.",
                        "Rico Hunt — aggregates live UAE listings from these sources and matches them against your CV automatically, so you stop manually checking five sites a day.",
                    ],
                    ar: [
                        "لينكدإن — القناة الأساسية للوظائف المهنية؛ فعّل التنبيهات وقدّم خلال 24–48 ساعة من نشر الإعلان.",
                        "بيت.كوم وNaukrigulf وGulfTalent — المواقع الإقليمية التي ينشر فيها كثير من أصحاب العمل المحليين أولاً.",
                        "Indeed وGlassdoor — يجمعان كثيراً من وظائف الإمارات بما فيها الشركات الصغيرة والمتوسطة.",
                        "صفحات التوظيف الخاصة بالشركات — الجهات الحكومية والبنوك وشركات الطيران والمجموعات الكبرى تنشر غالباً على مواقعها فقط.",
                        "شركات التوظيف (Hays وMichael Page وRobert Half والمتخصصون القطاعيون) — أساسية للأدوار المتوسطة والعليا.",
                        "ريكو هانت — يجمع وظائف الإمارات الحية من هذه المصادر ويطابقها مع سيرتك تلقائياً، فيغنيك عن تفقّد خمسة مواقع يومياً.",
                    ],
                },
            },
            {
                heading: {
                    en: "Step 4 — Apply fast, follow up, and track everything",
                    ar: "الخطوة 4 — قدّم بسرعة وتابع وسجّل كل شيء",
                },
                paragraphs: {
                    en: [
                        "Speed matters: applications in the first two days of a posting get disproportionate attention. Tailor the top third of your CV to each role, and keep a tracker of every application — company, role, date, contact, status. Follow up politely after 7–10 days of silence; in the UAE market a respectful follow-up message frequently revives a stalled application.",
                        "Expect a realistic timeline of 2–4 months for most professional roles if you are in-country, and longer from abroad. Consistency beats intensity: 10 targeted applications a week outperform 100 untargeted ones.",
                    ],
                    ar: [
                        "السرعة مهمة: الطلبات المقدمة في أول يومين من نشر الإعلان تحظى باهتمام غير متناسب. خصّص الثلث الأعلى من سيرتك لكل دور، واحتفظ بسجل لكل طلب — الشركة والدور والتاريخ وجهة الاتصال والحالة. تابع بأدب بعد 7–10 أيام من الصمت؛ في سوق الإمارات كثيراً ما تُحيي رسالة متابعة محترمة طلباً متوقفاً.",
                        "توقّع مدة واقعية من شهرين إلى أربعة أشهر لمعظم الأدوار المهنية إن كنت داخل الدولة، وأطول من الخارج. الاستمرارية تتفوق على الاندفاع: عشرة طلبات مستهدفة أسبوعياً أفضل من مئة طلب عشوائي.",
                    ],
                },
            },
            {
                heading: {
                    en: "The mistakes that cost applicants months",
                    ar: "الأخطاء التي تكلف المتقدمين شهوراً",
                },
                bullets: {
                    en: [
                        "Sending one generic CV to every role — ATS scoring punishes this immediately.",
                        "Ignoring salary research — quote ranges from Bayt and GulfTalent salary guides, not home-country figures.",
                        "Applying only to famous companies — most UAE hiring happens in SMEs and mid-size groups.",
                        "Going silent after applying — no follow-up means no visibility.",
                        "Paying anyone who \"guarantees\" a job or visa — legitimate employers and recruiters never charge candidates.",
                    ],
                    ar: [
                        "إرسال سيرة ذاتية واحدة عامة لكل الأدوار — تقييم ATS يعاقب هذا فوراً.",
                        "تجاهل أبحاث الرواتب — استشهد بنطاقات من أدلة رواتب بيت.كوم وGulfTalent، لا بأرقام بلدك الأصلي.",
                        "التقديم للشركات الشهيرة فقط — معظم التوظيف في الإمارات يحدث في الشركات الصغيرة والمتوسطة.",
                        "الصمت بعد التقديم — لا متابعة يعني لا حضور.",
                        "الدفع لأي جهة \"تضمن\" وظيفة أو تأشيرة — أصحاب العمل وشركات التوظيف الشرعية لا يتقاضون رسوماً من المرشحين أبداً.",
                    ],
                },
                paragraphs: {
                    en: [
                        "Want the searching, matching, and tracking handled for you? Create a free Rico Hunt account, upload your CV, and Rico surfaces matching UAE roles and tracks every application — in English or Arabic.",
                    ],
                    ar: [
                        "تريد من يتولى البحث والمطابقة والتتبع عنك؟ أنشئ حساباً مجانياً في ريكو هانت، وارفع سيرتك الذاتية، وسيعرض لك ريكو الوظائف المطابقة في الإمارات ويتتبع كل طلب — بالعربية أو الإنجليزية.",
                    ],
                },
            },
        ],
    },
    {
        slug: "uae-interview-questions-answers",
        title: {
            en: "Common Job Interview Questions in the UAE — and How to Answer Them",
            ar: "أسئلة مقابلات العمل الشائعة في الإمارات — وكيف تجيب عنها",
        },
        description: {
            en: "The questions UAE interviewers actually ask — salary expectations, notice period, visa status, culture fit — with strong sample answers in English and Arabic.",
            ar: "الأسئلة التي يطرحها المقابلون في الإمارات فعلاً — توقعات الراتب، فترة الإشعار، حالة التأشيرة، الملاءمة الثقافية — مع نماذج إجابات قوية بالعربية والإنجليزية.",
        },
        datePublished: "2026-07-21",
        dateModified: "2026-07-21",
        readingMinutes: 6,
        keywords: [
            "UAE interview questions",
            "Dubai job interview tips",
            "salary expectations UAE",
            "interview preparation Dubai",
            "أسئلة مقابلة العمل الإمارات",
        ],
        intro: {
            en: [
                "Interviews in the UAE mix standard competency questions with market-specific ones about salary, visa status, and availability — often in the first screening call. Being unprepared for these practical questions eliminates more candidates than any technical test.",
                "Here are the questions you should expect and how to answer them well.",
            ],
            ar: [
                "تمزج المقابلات في الإمارات بين أسئلة الكفاءة المعتادة وأسئلة خاصة بالسوق حول الراتب وحالة التأشيرة والجاهزية — غالباً في مكالمة الفرز الأولى. عدم الاستعداد لهذه الأسئلة العملية يستبعد مرشحين أكثر مما يستبعده أي اختبار تقني.",
                "إليك الأسئلة التي يجب أن تتوقعها وكيف تجيب عنها بشكل جيد.",
            ],
        },
        sections: [
            {
                heading: {
                    en: "\"What are your salary expectations?\"",
                    ar: "\"ما توقعاتك للراتب؟\"",
                },
                paragraphs: {
                    en: [
                        "This almost always comes up in the first call, and answering badly ends the process. Research the range for your role and seniority on Bayt, GulfTalent, and LinkedIn salary insights, then give a researched range rather than a single number: \"Based on the market for this role in Dubai, I'm looking at AED X–Y total package, and I'm flexible for the right opportunity.\" Always speak in total package terms (basic + housing + transport) — UAE offers are structured that way.",
                    ],
                    ar: [
                        "يُطرح هذا السؤال في المكالمة الأولى غالباً، والإجابة السيئة تنهي العملية. ابحث عن نطاق راتب دورك ومستواك على بيت.كوم وGulfTalent وبيانات لينكدإن، ثم قدّم نطاقاً مدروساً بدل رقم واحد: \"بناءً على السوق لهذا الدور في دبي، أتطلع إلى حزمة إجمالية بين X وY درهم، وأنا مرن للفرصة المناسبة.\" وتحدث دائماً بلغة الحزمة الإجمالية (الأساسي + السكن + المواصلات) — فهكذا تُهيكل العروض في الإمارات.",
                    ],
                },
            },
            {
                heading: {
                    en: "\"What is your visa status and notice period?\"",
                    ar: "\"ما حالة تأشيرتك وفترة الإشعار لديك؟\"",
                },
                paragraphs: {
                    en: [
                        "Answer factually and without hesitation — uncertainty here reads as risk. Good answers sound like: \"I'm on an employment visa with a 30-day notice period; it's transferable\", or \"I'm on a visit visa and can start immediately once the offer is issued.\" If you are abroad, acknowledge the relocation directly: \"I'm ready to relocate within X weeks of an offer; I have no dependents joining initially.\"",
                    ],
                    ar: [
                        "أجب بوقائع ودون تردد — فالتردد هنا يُقرأ كمخاطرة. الإجابات الجيدة تشبه: \"أنا على تأشيرة عمل بفترة إشعار 30 يوماً وقابلة للتحويل\"، أو \"أنا على تأشيرة زيارة وأستطيع البدء فوراً بعد صدور العرض.\" وإن كنت خارج الدولة، فواجه موضوع الانتقال مباشرة: \"أنا مستعد للانتقال خلال X أسابيع من العرض.\"",
                    ],
                },
            },
            {
                heading: {
                    en: "\"Why the UAE?\" / \"Why this company?\"",
                    ar: "\"لماذا الإمارات؟\" / \"لماذا هذه الشركة؟\"",
                },
                paragraphs: {
                    en: [
                        "Employers invest heavily in visas and onboarding, so they screen for commitment. Weak answers talk about lifestyle; strong answers connect your career plan to the market: \"The UAE is where the biggest projects in my field are happening, and this role puts me at the centre of them. I'm building a long-term career here, not a short stint.\" For the company question, reference something specific — a project, an expansion, a product — that shows you researched them.",
                    ],
                    ar: [
                        "يستثمر أصحاب العمل كثيراً في التأشيرات والتأهيل، لذا يفحصون مدى الالتزام. الإجابات الضعيفة تتحدث عن نمط الحياة؛ أما القوية فتربط خطتك المهنية بالسوق: \"الإمارات هي حيث تحدث أكبر المشاريع في مجالي، وهذا الدور يضعني في قلبها. أنا أبني مسيرة طويلة الأمد هنا، لا محطة قصيرة.\" ولسؤال الشركة، أشر إلى شيء محدد — مشروع أو توسّع أو منتج — يُظهر أنك بحثت عنهم.",
                    ],
                },
            },
            {
                heading: {
                    en: "Competency questions: use the STAR structure",
                    ar: "أسئلة الكفاءة: استخدم هيكل STAR",
                },
                paragraphs: {
                    en: [
                        "For \"tell me about a time when...\" questions, structure every answer as Situation, Task, Action, Result — with a measurable result. UAE interviewers, especially in multinational and government-linked organisations, also probe cross-cultural teamwork: prepare one concrete story about collaborating successfully in a multicultural team, since most UAE workplaces span dozens of nationalities.",
                    ],
                    ar: [
                        "لأسئلة \"حدثني عن موقف...\"، ابنِ كل إجابة على هيكل STAR: الموقف، المهمة، الإجراء، النتيجة — مع نتيجة قابلة للقياس. كما يختبر المقابلون في الإمارات، خصوصاً في الشركات متعددة الجنسيات والجهات الحكومية، العمل الجماعي عبر الثقافات: جهّز قصة ملموسة واحدة عن تعاون ناجح في فريق متعدد الثقافات، فمعظم بيئات العمل الإماراتية تضم عشرات الجنسيات.",
                    ],
                },
            },
            {
                heading: {
                    en: "Practise before it counts",
                    ar: "تدرّب قبل أن تصبح المقابلة حقيقية",
                },
                paragraphs: {
                    en: [
                        "The difference between knowing an answer and delivering it under pressure is practice. Rico Hunt's AI interview preparation lets you rehearse role-specific questions — including salary and visa questions phrased the way UAE recruiters actually ask them — and gives instant feedback, in English or Arabic. Start free at ricohunt.com.",
                    ],
                    ar: [
                        "الفرق بين معرفة الإجابة وتقديمها تحت الضغط هو التدريب. تتيح لك ميزة الاستعداد للمقابلات بالذكاء الاصطناعي في ريكو هانت التمرن على أسئلة خاصة بدورك — بما فيها أسئلة الراتب والتأشيرة بالصياغة التي يستخدمها مسؤولو التوظيف في الإمارات فعلاً — مع ملاحظات فورية، بالعربية أو الإنجليزية. ابدأ مجاناً على ricohunt.com.",
                    ],
                },
            },
        ],
    },
];

export function getPostBySlug(slug: string): BlogPost | undefined {
    return POSTS.find((post) => post.slug === slug);
}
