"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { FormEvent, useState } from "react";

const LOCATIONS = [
  "Abu Dhabi",
  "Dubai",
  "Sharjah",
  "Ajman",
  "Umm Al Quwain",
  "Ras Al Khaimah",
  "Fujairah",
  "Outside UAE",
] as const;

type Status = "idle" | "submitting" | "success" | "error";

const COPY = {
  en: {
    email: "Email address *",
    firstName: "First name (optional)",
    role: "Target role (optional)",
    location: "Location (optional)",
    consent:
      "I agree to receive Rico launch and early-access updates. I can unsubscribe at any time.",
    submit: "Reserve early access",
    submitting: "Reserving…",
    successTitle: "Your place is reserved.",
    successBody: "We recorded your early-access request.",
    genericError: "Registration is temporarily unavailable. Please try again.",
  },
  ar: {
    email: "البريد الإلكتروني *",
    firstName: "الاسم الأول (اختياري)",
    role: "الوظيفة المستهدفة (اختياري)",
    location: "الموقع (اختياري)",
    consent:
      "أوافق على استلام تحديثات إطلاق ريكو والوصول المبكر، ويمكنني إلغاء الاشتراك في أي وقت.",
    submit: "احجز وصولك المبكر",
    submitting: "جارٍ الحجز…",
    successTitle: "تم حجز مكانك.",
    successBody: "سجّلنا طلب الوصول المبكر الخاص بك.",
    genericError: "التسجيل غير متاح مؤقتًا. حاول مرة أخرى.",
  },
};

export function WaitlistForm() {
  const { language } = useLanguage();
  const copy = COPY[language];
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [location, setLocation] = useState("");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email || !consent || status === "submitting") return;

    setStatus("submitting");
    setMessage("");

    const params = new URLSearchParams(window.location.search);
    const source = Object.fromEntries(
      [
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "referral_code",
      ]
        .map((key) => [key, params.get(key)] as const)
        .filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    source.landing_path = window.location.pathname;

    try {
      const response = await fetch("/proxy/api/v1/waitlist/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          first_name: firstName || null,
          target_role: targetRole || null,
          location: location || null,
          consent: true,
          source,
        }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        message?: string;
        detail?: string;
      };

      if (!response.ok) {
        throw new Error(data.detail || copy.genericError);
      }

      setStatus("success");
      setMessage(data.message || copy.successBody);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : copy.genericError);
    }
  }

  if (status === "success") {
    return (
      <div className="atl-waitlist-success" role="status" aria-live="polite">
        <strong>{copy.successTitle}</strong>
        <span>{message}</span>
      </div>
    );
  }

  return (
    <form className="atl-waitlist-form" onSubmit={handleSubmit} aria-label={copy.submit}>
      <label className="atl-waitlist-sr" htmlFor="waitlist-email">
        {copy.email}
      </label>
      <input
        id="waitlist-email"
        type="email"
        autoComplete="email"
        required
        maxLength={256}
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder={copy.email}
      />

      <div className="atl-waitlist-grid">
        <div>
          <label className="atl-waitlist-sr" htmlFor="waitlist-name">
            {copy.firstName}
          </label>
          <input
            id="waitlist-name"
            type="text"
            autoComplete="given-name"
            maxLength={100}
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            placeholder={copy.firstName}
          />
        </div>
        <div>
          <label className="atl-waitlist-sr" htmlFor="waitlist-role">
            {copy.role}
          </label>
          <input
            id="waitlist-role"
            type="text"
            maxLength={200}
            value={targetRole}
            onChange={(event) => setTargetRole(event.target.value)}
            placeholder={copy.role}
          />
        </div>
      </div>

      <label className="atl-waitlist-sr" htmlFor="waitlist-location">
        {copy.location}
      </label>
      <select
        id="waitlist-location"
        value={location}
        onChange={(event) => setLocation(event.target.value)}
      >
        <option value="">{copy.location}</option>
        {LOCATIONS.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>

      <label className="atl-waitlist-consent" htmlFor="waitlist-consent">
        <input
          id="waitlist-consent"
          type="checkbox"
          required
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
        />
        <span>{copy.consent}</span>
      </label>

      {status === "error" && (
        <p className="atl-waitlist-error" role="alert" aria-live="assertive">
          {message}
        </p>
      )}

      <button type="submit" disabled={!email || !consent || status === "submitting"}>
        {status === "submitting" ? copy.submitting : copy.submit}
      </button>
    </form>
  );
}
