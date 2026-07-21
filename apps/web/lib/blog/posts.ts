// Static bilingual career-guide content for the public /blog section.
// Pure data module (no React) so it can be imported from both server
// components (metadata, JSON-LD, sitemap) and client components (rendering).
//
// Arabic copy is authored directly in Arabic (Gulf professional register),
// not translated sentence-by-sentence from the English — the two versions
// carry the same substance but each reads natively.
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
            ar: "كيف تكتب سيرة ذاتية تجتاز الفرز الآلي (ATS) في الإمارات؟ دليل 2026",
        },
        description: {
            en: "Most CVs in the UAE are rejected by ATS software before a human reads them. Learn the format, keywords, and structure that get your CV past the filters and in front of recruiters in Dubai and Abu Dhabi.",
            ar: "أغلب السير الذاتية في الإمارات تُستبعد آلياً قبل أن تصل إلى يد إنسان. تعرّف على التنسيق الصحيح وطريقة اختيار الكلمات المفتاحية حتى تصل سيرتك إلى مسؤولي التوظيف في دبي وأبوظبي.",
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
                "قبل أن يفتح مسؤول التوظيف سيرتك الذاتية، تمرّ في معظم الشركات المتوسطة والكبيرة بالإمارات على نظام فرز آلي يُعرف بنظام تتبع المتقدمين (ATS). فإن عجز النظام عن قراءتها، استُبعدت مهما بلغت خبرتك.",
                "في هذا الدليل نشرح قواعد التنسيق، وطريقة اختيار الكلمات المفتاحية، والتفاصيل التي يتوقعها سوق العمل الإماراتي تحديداً، حتى تتجاوز سيرتك مرحلة الفرز الآلي في دبي وأبوظبي وسائر الإمارات.",
            ],
        },
        sections: [
            {
                heading: {
                    en: "What an ATS actually does with your CV",
                    ar: "ماذا يفعل نظام ATS بسيرتك؟",
                },
                paragraphs: {
                    en: [
                        "An ATS parses your CV into structured fields — name, contact, work history, skills — then scores it against the job description. Recruiters typically review only the top-ranked profiles. Two things break this process: formatting the parser cannot read, and missing keywords the scoring engine expects.",
                    ],
                    ar: [
                        "يقرأ النظام سيرتك ويحوّلها إلى حقول منظمة: الاسم، وبيانات التواصل، والخبرات، والمهارات، ثم يقارنها بالوصف الوظيفي ويمنحها درجة. ولا يصل إلى مسؤول التوظيف عادةً إلا أصحاب الدرجات الأعلى. وتسقط السيرة لسببين رئيسيين: تنسيق لا يستطيع النظام قراءته، أو غياب الكلمات المفتاحية التي يبحث عنها.",
                    ],
                },
            },
            {
                heading: {
                    en: "Formatting rules that pass the parser",
                    ar: "قواعد تنسيق تضمن قراءة سليمة",
                },
                paragraphs: {
                    en: [
                        "Keep the file simple and predictable. Decorative templates that look impressive to humans are the most common reason CVs fail parsing.",
                    ],
                    ar: [
                        "اجعل ملفك بسيطاً وواضحاً؛ فالقوالب المزخرفة التي تُبهر العين هي أكثر ما يوقع السير الذاتية في فخ الفرز الآلي.",
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
                        "اعتمد تصميماً بعمود واحد؛ فالجداول ومربعات النص والأعمدة المزدوجة تخلط ترتيب المحتوى عند القراءة الآلية.",
                        "احفظ الملف بصيغة ‎.docx أو PDF نصي، وإياك والصور الممسوحة ضوئياً.",
                        "استخدم عناوين الأقسام المتعارف عليها: الخبرة العملية، التعليم، المهارات، الشهادات.",
                        "لا تضع بيانات التواصل في ترويسة الصفحة أو تذييلها؛ فبعض الأنظمة لا تقرؤهما أصلاً.",
                        "التزم بخط واضح مثل Arial أو Calibri بحجم 10 إلى 12، واستغنِ عن الأيقونات والرسوم.",
                    ],
                },
            },
            {
                heading: {
                    en: "Keyword strategy: mirror the job description",
                    ar: "الكلمات المفتاحية: خاطِب الإعلان بلغته",
                },
                paragraphs: {
                    en: [
                        "ATS scoring is largely keyword matching. Read the job description and use its exact terminology — if the posting says \"accounts payable\", write \"accounts payable\", not just \"AP\". Include both the spelled-out form and the abbreviation for key terms (e.g. \"Customer Relationship Management (CRM)\").",
                        "Place your most important keywords in three locations: the professional summary at the top, the skills section, and inside actual work-experience bullet points. Keywords listed only in a skills section without supporting experience score lower on modern systems.",
                    ],
                    ar: [
                        "التقييم الآلي في جوهره مطابقة كلمات. اقرأ الإعلان الوظيفي بتمعّن واستخدم مصطلحاته كما وردت حرفياً؛ فإن ذكر «حسابات الموردين» فاكتبها بالنص نفسه. واذكر المصطلحات المهمة بصيغتها الكاملة واختصارها معاً، مثل: إدارة علاقات العملاء (CRM).",
                        "ثم وزّع أهم الكلمات على ثلاثة مواضع: الملخص المهني في المقدمة، وقسم المهارات، ونقاط الخبرة العملية نفسها. أما الكلمات المحشورة في قسم المهارات وحده دون خبرة تسندها، فلا تمنحك في الأنظمة الحديثة إلا درجة متواضعة.",
                    ],
                },
            },
            {
                heading: {
                    en: "UAE-specific CV details",
                    ar: "ما يتوقعه سوق الإمارات في سيرتك",
                },
                paragraphs: {
                    en: [
                        "The UAE market has its own conventions that both ATS filters and recruiters expect to see.",
                    ],
                    ar: [
                        "لسوق العمل الخليجي أعراف يعرفها مسؤولو التوظيف وتراعيها أنظمة الفرز. احرص على ما يلي:",
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
                        "اذكر مكان إقامتك وحالة تأشيرتك بوضوح، مثل: «مقيم في دبي — تأشيرة عمل قابلة للتحويل»؛ فهذا من أول ما يُفرز المتقدمون على أساسه.",
                        "أدرج جنسيتك واللغات التي تتقنها؛ فهذا متعارف عليه في دول الخليج، وكثير من عمليات البحث تُبنى عليه.",
                        "اذكر فترة الإشعار، وإن كنت متاحاً فوراً فقلها صراحةً؛ فهي ميزة تنافسية حقيقية في سوق سريع الإيقاع.",
                        "استخدم رقم هاتف إماراتياً (‎+971) إن توفر لديك؛ فبعض المسؤولين يتجاوزون الأرقام الأجنبية.",
                        "اجعل سيرتك في صفحتين على الأكثر، وثلاث صفحات للمناصب القيادية.",
                    ],
                },
            },
            {
                heading: {
                    en: "Test your CV before you apply",
                    ar: "اختبر سيرتك قبل أن ترسلها",
                },
                paragraphs: {
                    en: [
                        "Before sending applications, check how software actually reads your CV: copy-paste the file's text into a plain text editor — if the order is scrambled or sections are missing, an ATS will see the same mess.",
                        "Rico Hunt does this automatically: upload your CV and Rico analyses it against real UAE job descriptions, shows your match score per role, and suggests targeted edits — in English or Arabic. It's free to start at ricohunt.com.",
                    ],
                    ar: [
                        "أبسط اختبار: انسخ نص سيرتك والصقه في محرر نصوص عادي. فإن وجدت الترتيب مختلطاً أو بعض الأقسام مفقودة، فاعلم أن نظام الفرز سيرى الخلل نفسه.",
                        "أو دع ريكو يتكفل بالأمر: ارفع سيرتك على ريكو هانت ليحللها مقابل إعلانات وظائف حقيقية في الإمارات، ويعرض لك درجة توافقك مع كل وظيفة، ويقترح تحسينات محددة — بالعربية أو الإنجليزية. ابدأ مجاناً على ricohunt.com.",
                    ],
                },
            },
        ],
    },
    {
        slug: "find-job-dubai-uae-2026",
        title: {
            en: "How to Find a Job in Dubai and the UAE in 2026: Step-by-Step",
            ar: "كيف تحصل على وظيفة في دبي والإمارات في 2026؟ دليل خطوة بخطوة",
        },
        description: {
            en: "A practical, up-to-date roadmap for landing a job in Dubai, Abu Dhabi, or anywhere in the UAE — visas, job boards, recruiters, timelines, and the mistakes that cost applicants months.",
            ar: "خارطة طريق عملية للحصول على وظيفة في دبي أو أبوظبي أو أي إمارة أخرى: التأشيرات، ومواقع التوظيف، وشركات التوظيف، والمدة المتوقعة للبحث، والأخطاء التي تهدر شهوراً.",
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
                "ما زالت الإمارات من أنشط أسواق التوظيف في المنطقة، لكنها أيضاً من أشدها منافسة؛ فالإعلان الواحد في المجالات المطلوبة قد يستقبل مئات الطلبات. والفارق بين من يظفر بوظيفة خلال ثلاثة أشهر ومن يبحث سنة كاملة هو طريقة البحث، لا الحظ.",
                "هذه هي الخطوات التي أثبتت جدواها في سوق الإمارات.",
            ],
        },
        sections: [
            {
                heading: {
                    en: "Step 1 — Understand your visa position first",
                    ar: "أولاً: اعرف وضع تأشيرتك",
                },
                paragraphs: {
                    en: [
                        "Employers sort candidates into \"inside the country and available\" versus \"needs relocation and sponsorship\". If you are already in the UAE on any valid visa (visit, spouse, golden, or a transferable employment visa), say so at the top of your CV — it materially increases response rates. If you are applying from abroad, target larger companies and free-zone employers that regularly sponsor international hires, and expect a longer timeline.",
                    ],
                    ar: [
                        "يصنّف أصحاب العمل المتقدمين إلى فئتين: موجود داخل الدولة وجاهز للمباشرة، أو قادم من الخارج ويحتاج إلى استقدام وكفالة. فإن كنت داخل الإمارات بأي تأشيرة سارية — زيارة، أو إقامة عائلية، أو تأشيرة ذهبية، أو تأشيرة عمل قابلة للتحويل — فاذكر ذلك في أعلى سيرتك؛ فهو يرفع فرص الرد عليك رفعاً ملحوظاً. وإن كنت تتقدم من الخارج، فوجّه طلباتك إلى الشركات الكبرى وشركات المناطق الحرة المعتادة على استقدام الموظفين من الخارج، وتوقّع أن يطول بحثك.",
                    ],
                },
            },
            {
                heading: {
                    en: "Step 2 — Fix your CV and LinkedIn before applying anywhere",
                    ar: "ثانياً: جهّز سيرتك وحسابك على لينكدإن قبل أي طلب",
                },
                paragraphs: {
                    en: [
                        "Applying with a weak CV burns opportunities you cannot re-apply to for months. Make your CV ATS-friendly (see our dedicated guide), then align your LinkedIn headline and location to Dubai/UAE — recruiters in the Emirates source heavily from LinkedIn search, and your location field is a filter.",
                    ],
                    ar: [
                        "التقديم بسيرة ضعيفة يحرق فرصاً قد لا تتكرر قريباً. ابدأ بجعل سيرتك متوافقة مع أنظمة الفرز الآلي (راجع دليلنا المخصص لذلك)، ثم حدّث حسابك على لينكدإن واجعل موقعك فيه دبي أو الإمارات؛ فمسؤولو التوظيف هناك يبحثون عن المرشحين عبر لينكدإن أولاً، وحقل الموقع عندهم فلتر أساسي.",
                    ],
                },
            },
            {
                heading: {
                    en: "Step 3 — Cover every serious job channel",
                    ar: "ثالثاً: لا تكتفِ بموقع واحد",
                },
                paragraphs: {
                    en: [
                        "No single job board covers the UAE market. A serious search runs across all of these in parallel:",
                    ],
                    ar: [
                        "لا يغطي أي موقع بمفرده سوق الإمارات كاملاً، والبحث الجاد يجري في هذه القنوات كلها بالتوازي:",
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
                        "لينكدإن: القناة الأولى للوظائف المهنية. فعّل التنبيهات وقدّم خلال يوم أو يومين من نشر الإعلان.",
                        "بيت.كوم وNaukrigulf وGulfTalent: مواقع إقليمية يبدأ بها كثير من أصحاب العمل المحليين.",
                        "Indeed وGlassdoor: يجمعان عدداً كبيراً من وظائف الإمارات، ومنها وظائف الشركات الصغيرة والمتوسطة.",
                        "مواقع الشركات نفسها: الجهات الحكومية والبنوك وشركات الطيران والمجموعات الكبرى كثيراً ما تنشر شواغرها على صفحاتها فقط.",
                        "شركات التوظيف مثل Hays وMichael Page وRobert Half: طريق شبه إلزامي للمناصب المتوسطة والعليا.",
                        "ريكو هانت: يجمع الوظائف الحية من هذه المصادر ويطابقها مع سيرتك تلقائياً، فيغنيك عن تفقّد خمسة مواقع كل يوم.",
                    ],
                },
            },
            {
                heading: {
                    en: "Step 4 — Apply fast, follow up, and track everything",
                    ar: "رابعاً: قدّم مبكراً، وتابع، وسجّل كل شيء",
                },
                paragraphs: {
                    en: [
                        "Speed matters: applications in the first two days of a posting get disproportionate attention. Tailor the top third of your CV to each role, and keep a tracker of every application — company, role, date, contact, status. Follow up politely after 7–10 days of silence; in the UAE market a respectful follow-up message frequently revives a stalled application.",
                        "Expect a realistic timeline of 2–4 months for most professional roles if you are in-country, and longer from abroad. Consistency beats intensity: 10 targeted applications a week outperform 100 untargeted ones.",
                    ],
                    ar: [
                        "للسرعة أثر كبير؛ فالطلبات التي تصل في اليومين الأولين تنال نصيب الأسد من الاهتمام. خصص الجزء الأول من سيرتك لكل وظيفة على حدة، واحتفظ بسجل يضم كل طلب: الشركة، والوظيفة، والتاريخ، وجهة التواصل، وحالة الطلب. وإن مضى أسبوع إلى عشرة أيام بلا رد، فأرسل رسالة متابعة مهذبة؛ فكثيراً ما تفتح باباً بدا مغلقاً.",
                        "وكن واقعياً في توقعاتك: يحتاج معظم الباحثين داخل الدولة إلى ما بين شهرين وأربعة أشهر، وأكثر من ذلك لمن يتقدم من الخارج. والعبرة بالمواظبة لا بالكثرة: عشرة طلبات مدروسة في الأسبوع خيرٌ من مئة طلب عشوائي.",
                    ],
                },
            },
            {
                heading: {
                    en: "The mistakes that cost applicants months",
                    ar: "أخطاء تهدر شهوراً من البحث",
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
                        "إرسال السيرة نفسها إلى كل الوظائف؛ فالفرز الآلي يكشف ذلك ويعاقب عليه فوراً.",
                        "إهمال دراسة الرواتب؛ استند إلى أدلة رواتب بيت.كوم وGulfTalent، لا إلى رواتب بلدك الأصلي.",
                        "حصر الطلبات في الشركات الشهيرة، مع أن معظم التوظيف يجري في الشركات الصغيرة والمتوسطة.",
                        "الانقطاع عن المتابعة بعد التقديم؛ فمن لا يُتابع يُنسى.",
                        "دفع المال لمن يعدك بوظيفة أو تأشيرة «مضمونة»؛ فالجهات الموثوقة لا تتقاضى من الباحث عن عمل شيئاً.",
                    ],
                },
                paragraphs: {
                    en: [
                        "Want the searching, matching, and tracking handled for you? Create a free Rico Hunt account, upload your CV, and Rico surfaces matching UAE roles and tracks every application — in English or Arabic.",
                    ],
                    ar: [
                        "وإن أردت من يتولى عنك البحث والمطابقة والمتابعة، فأنشئ حساباً مجانياً على ريكو هانت وارفع سيرتك؛ ليعرض عليك الوظائف المناسبة في الإمارات ويتتبع طلباتك أولاً بأول — بالعربية أو الإنجليزية.",
                    ],
                },
            },
        ],
    },
    {
        slug: "uae-interview-questions-answers",
        title: {
            en: "Common Job Interview Questions in the UAE — and How to Answer Them",
            ar: "أسئلة تتكرر في مقابلات العمل بالإمارات — وكيف تجيب عنها بثقة",
        },
        description: {
            en: "The questions UAE interviewers actually ask — salary expectations, notice period, visa status, culture fit — with strong sample answers in English and Arabic.",
            ar: "الأسئلة التي تتكرر فعلاً في مقابلات العمل بالإمارات — الراتب المتوقع، وفترة الإشعار، وحالة التأشيرة، وسبب اختيارك للشركة — مع نماذج إجابات قوية بالعربية والإنجليزية.",
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
                "تجمع المقابلات في الإمارات بين أسئلة الكفاءة المعروفة وأسئلة عملية يتميز بها هذا السوق: الراتب، والتأشيرة، وموعد المباشرة — وغالباً ما تُطرح في مكالمة الفرز الأولى. وقلة الاستعداد لهذه الأسئلة تُقصي من المرشحين أكثر مما تُقصيه الاختبارات الفنية.",
                "هذه أبرز الأسئلة، وطريقة الإجابة عنها.",
            ],
        },
        sections: [
            {
                heading: {
                    en: "\"What are your salary expectations?\"",
                    ar: "«ما الراتب الذي تتوقعه؟»",
                },
                paragraphs: {
                    en: [
                        "This almost always comes up in the first call, and answering badly ends the process. Research the range for your role and seniority on Bayt, GulfTalent, and LinkedIn salary insights, then give a researched range rather than a single number: \"Based on the market for this role in Dubai, I'm looking at AED X–Y total package, and I'm flexible for the right opportunity.\" Always speak in total package terms (basic + housing + transport) — UAE offers are structured that way.",
                    ],
                    ar: [
                        "يأتي هذا السؤال في أول مكالمة غالباً، والإجابة المرتجلة قد تنهي مسارك قبل أن يبدأ. ابحث أولاً عن نطاق رواتب وظيفتك ومستواك في أدلة بيت.كوم وGulfTalent وبيانات لينكدإن، ثم أجب بنطاق لا برقم واحد: «بحسب السوق لهذا الدور في دبي، أتطلع إلى حزمة إجمالية بين كذا وكذا، وعندي مرونة إن كانت الفرصة مناسبة». وتحدث دائماً عن الحزمة الإجمالية — الراتب الأساسي وبدل السكن والمواصلات — فهكذا تُبنى العروض في الإمارات.",
                    ],
                },
            },
            {
                heading: {
                    en: "\"What is your visa status and notice period?\"",
                    ar: "«ما حالة تأشيرتك؟ وكم فترة الإشعار عندك؟»",
                },
                paragraphs: {
                    en: [
                        "Answer factually and without hesitation — uncertainty here reads as risk. Good answers sound like: \"I'm on an employment visa with a 30-day notice period; it's transferable\", or \"I'm on a visit visa and can start immediately once the offer is issued.\" If you are abroad, acknowledge the relocation directly: \"I'm ready to relocate within X weeks of an offer; I have no dependents joining initially.\"",
                    ],
                    ar: [
                        "أجب بمعلومة واضحة ومن غير تلعثم؛ فالتردد هنا يوحي بمخاطرة لا يريدها صاحب العمل. من الإجابات الجيدة: «أحمل تأشيرة عمل قابلة للتحويل، وفترة الإشعار عندي ثلاثون يوماً»، أو «أنا على تأشيرة زيارة وأستطيع المباشرة فور صدور العرض». وإن كنت خارج الدولة فصارِح بوضعك: «جاهز للانتقال خلال أسابيع قليلة من استلام العرض».",
                    ],
                },
            },
            {
                heading: {
                    en: "\"Why the UAE?\" / \"Why this company?\"",
                    ar: "«لماذا الإمارات؟» و«لماذا شركتنا؟»",
                },
                paragraphs: {
                    en: [
                        "Employers invest heavily in visas and onboarding, so they screen for commitment. Weak answers talk about lifestyle; strong answers connect your career plan to the market: \"The UAE is where the biggest projects in my field are happening, and this role puts me at the centre of them. I'm building a long-term career here, not a short stint.\" For the company question, reference something specific — a project, an expansion, a product — that shows you researched them.",
                    ],
                    ar: [
                        "صاحب العمل يتحمل كلفة التأشيرة والاستقدام والتأهيل، فهو يبحث عمن يبقى. والإجابات التي تدور حول نمط الحياة وحده ضعيفة؛ أما القوية فتربط خطتك المهنية بالسوق: «أكبر مشاريع مجالي تجري اليوم في الإمارات، وهذا الدور يضعني في قلبها؛ أنا أبني هنا مسيرة طويلة، لا محطة عابرة». وعن الشركة، اذكر شيئاً محدداً — مشروعاً أو توسعاً أو منتجاً — يدل على أنك قرأت عنها فعلاً.",
                    ],
                },
            },
            {
                heading: {
                    en: "Competency questions: use the STAR structure",
                    ar: "أسئلة الكفاءة: أجب بأسلوب STAR",
                },
                paragraphs: {
                    en: [
                        "For \"tell me about a time when...\" questions, structure every answer as Situation, Task, Action, Result — with a measurable result. UAE interviewers, especially in multinational and government-linked organisations, also probe cross-cultural teamwork: prepare one concrete story about collaborating successfully in a multicultural team, since most UAE workplaces span dozens of nationalities.",
                    ],
                    ar: [
                        "حين يُطلب منك أن تروي موقفاً من عملك، فرتّب إجابتك في أربع خطوات: الموقف، فالمهمة، فما فعلته، فالنتيجة — واجعل النتيجة رقماً يُقاس ما أمكن. واستعد كذلك لسؤال شائع عن العمل مع جنسيات متعددة؛ فبيئات العمل في الإمارات تجمع عشرات الجنسيات، وهذه الجاهزية تُختبر خصوصاً في الشركات الكبرى والجهات الحكومية. جهّز قصة واحدة محكمة عن تعاون ناجح في فريق متعدد الثقافات.",
                    ],
                },
            },
            {
                heading: {
                    en: "Practise before it counts",
                    ar: "تدرّب قبل المقابلة الحقيقية",
                },
                paragraphs: {
                    en: [
                        "The difference between knowing an answer and delivering it under pressure is practice. Rico Hunt's AI interview preparation lets you rehearse role-specific questions — including salary and visa questions phrased the way UAE recruiters actually ask them — and gives instant feedback, in English or Arabic. Start free at ricohunt.com.",
                    ],
                    ar: [
                        "شتّان بين من يعرف الإجابة ومن يتقنها تحت الضغط، والجسر بينهما هو التدريب. في ريكو هانت تتدرب على أسئلة مقابلات مصممة لوظيفتك تحديداً — ومنها أسئلة الراتب والتأشيرة بالصياغة التي يستخدمها مسؤولو التوظيف في الإمارات فعلاً — وتحصل على ملاحظات فورية، بالعربية أو الإنجليزية. ابدأ مجاناً على ricohunt.com.",
                    ],
                },
            },
        ],
    },
];

export function getPostBySlug(slug: string): BlogPost | undefined {
    return POSTS.find((post) => post.slug === slug);
}
