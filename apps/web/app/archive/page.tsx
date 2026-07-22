'use client';

import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { EmptySearchInk } from '@/components/illustrations/EditorialInk';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { useAuth } from '@/hooks/useAuth';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation } from '@/lib/translations';
import { fetchChatHistory, logout as apiLogout, type ChatHistoryMessage } from '@/lib/api';
import { useRouter } from 'next/navigation';
import React, { useCallback, useEffect, useState } from 'react';

type StructuredArchiveMessage = {
  type?: string;
  message?: string;
  matches?: unknown[];
};

function summarize(content: string): string {
  const text = content.replace(/\s+/g, ' ').trim();
  return text.length > 140 ? `${text.slice(0, 137)}...` : text;
}

function formatTimestamp(timestamp?: string | null): string {
  if (!timestamp) return 'Recent';
  return new Date(timestamp).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function parseStructuredAssistantMessage(message: ChatHistoryMessage): StructuredArchiveMessage | null {
  if (message.role !== 'assistant') {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(message.content);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null;
    }

    const record = parsed as Record<string, unknown>;
    return {
      type: typeof record.type === 'string' ? record.type : undefined,
      message: typeof record.message === 'string' ? record.message : undefined,
      matches: Array.isArray(record.matches) ? record.matches : undefined,
    };
  } catch {
    return null;
  }
}

export default function ArchivePage() {
  const [messages, setMessages] = useState<ChatHistoryMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const { user } = useAuth();
  const router = useRouter();
  const { language } = useLanguage();
  const t = useTranslation(language);

  const handleLogout = useCallback(async () => {
    try { await apiLogout(); } finally { router.push('/login'); }
  }, [router]);

  const loadArchive = useCallback(async () => {
    try {
      const response = await fetchChatHistory(8);
      setMessages(response.messages);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadArchive();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadArchive]);

  return (
    <AppShell
      title={t("archiveTitle")}
      subtitle={t("archiveSubtitle")}
      sidebarProps={{
        user: user ? { name: user.name, email: user.email } : undefined,
        onLogout: handleLogout,
      }}
    >
      {loading ? (
        <LoadingState variant="card" message={t("archiveLoading")} />
      ) : error ? (
        <ErrorState
          variant="network"
          message={t("archiveErrLoad")}
          onRetry={loadArchive}
        />
      ) : messages.length === 0 ? (
        <EmptyState
          illustration={<EmptySearchInk className="h-28 w-28 text-text-secondary" />}
          title={t("archiveEmptyTitle")}
          description={t("archiveEmptyDesc")}
          actionLabel={t("archiveOpenCommand")}
          actionHref="/command"
        />
      ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {messages.map((message, index) => {
              const structured = parseStructuredAssistantMessage(message);

              return (
                <GlassPanel key={`${message.timestamp ?? 'recent'}-${index}`} className="p-6 rounded-xl border border-white/10 hover:border-primary/30 transition-all group">
                  <div className="flex items-start justify-between mb-4 gap-4">
                    <h3 className="font-headline-lg text-headline-lg text-on-surface">{formatTimestamp(message.timestamp)}</h3>
                    <MaterialIcon icon="history" className="text-on-surface-variant/40 group-hover:text-primary transition-colors shrink-0" />
                  </div>
                  <div className="mb-4">
                    <p className="text-body-md text-on-surface-variant mb-2">
                      {message.role === 'user' ? t("archiveUserInstruction") : t("archiveRicoResponse")}
                    </p>
                    {structured ? (
                      <div className="space-y-2">
                        {structured.type && (
                          <span className="inline-block px-2 py-0.5 rounded bg-primary/10 text-[10px] text-primary font-medium tracking-wide uppercase">
                            {structured.type.replace(/_/g, ' ')}
                          </span>
                        )}
                        <p className="text-[12px] text-on-surface-variant/80 italic">
                          {summarize(structured.message ?? message.content)}
                        </p>
                        {structured.matches && structured.matches.length > 0 && (
                          <p className="text-[10px] text-secondary">
                            {structured.matches.length} {structured.matches.length !== 1 ? t("archiveMatchesFound") : t("archiveMatchFound")}
                          </p>
                        )}
                      </div>
                    ) : (
                      <p className="text-[12px] text-on-surface-variant/60 italic">{summarize(message.content)}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${message.role === 'user' ? 'bg-secondary' : 'bg-primary'}`} />
                    <span className="text-label-caps text-[10px] text-primary">{t("archiveMemoryIntegrated")}</span>
                  </div>
                </GlassPanel>
              );
            })}
          </div>
        )}
    </AppShell>
  );
}
