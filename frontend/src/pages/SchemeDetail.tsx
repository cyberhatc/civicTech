import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/lib/api";

interface SchemeSection {
  id: string;
  title: string;
  title_hi: string;
  body: string;
  body_hi: string;
  eligibility?: string[];
  eligibility_hi?: string[];
  documents?: string[];
  documents_hi?: string[];
  source: string;
  page: number;
}

interface Scheme {
  id: string;
  name: string;
  name_hi: string;
  short_name: string;
  category: string;
  category_hi: string;
  authority: string;
  state: string;
  launched: string;
  summary: string;
  summary_hi: string;
  amount: string;
  icon: string;
  sections: SchemeSection[];
}

export default function SchemeDetail() {
  const { id } = useParams<{ id: string }>();
  const [scheme, setScheme] = useState<Scheme | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .scheme(id)
      .then((data) => setScheme(data.scheme as unknown as Scheme))
      .catch((err) => setError(err instanceof Error ? err.message : "योजना नहीं मिली।"));
  }, [id]);

  return (
    <div className="min-h-dvh bg-ink-50">
      <header className="sticky top-0 z-20 border-b border-ink-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <Link to="/" className="rounded-lg border border-ink-200 px-2.5 py-1.5 text-sm text-ink-600 hover:bg-ink-100">
            ←
          </Link>
          <p className="text-sm font-bold text-ink-900">योजना का विवरण</p>
        </div>
      </header>

      <main className="mx-auto max-w-2xl space-y-4 px-4 py-6">
        {error && (
          <div role="alert" className="rounded-xl border border-alert-500/30 bg-alert-500/10 px-4 py-3 text-sm text-alert-700">
            {error}
          </div>
        )}

        {scheme && (
          <>
            <section className="surface p-5">
              <div className="flex items-start gap-3">
                <span aria-hidden="true" className="text-3xl">
                  {scheme.icon}
                </span>
                <div>
                  <h1 className="text-xl font-extrabold text-ink-900">{scheme.name_hi}</h1>
                  <p className="text-sm font-medium text-ink-500">
                    {scheme.short_name} · {scheme.category_hi}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-ink-700">{scheme.summary_hi}</p>
              <dl className="mt-4 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-ink-400">लाभ</dt>
                  <dd className="font-medium text-ink-800">{scheme.amount}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-ink-400">किसने शुरू की</dt>
                  <dd className="font-medium text-ink-800">{scheme.authority}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-ink-400">कहाँ लागू</dt>
                  <dd className="font-medium text-ink-800">{scheme.state}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-ink-400">शुरुआत</dt>
                  <dd className="font-medium text-ink-800">{scheme.launched}</dd>
                </div>
              </dl>
            </section>

            {scheme.sections.map((section) => (
              <section key={section.id} className="surface p-5">
                <h2 className="text-base font-bold text-ink-900">{section.title_hi}</h2>
                <p className="mt-2 text-sm leading-relaxed text-ink-700">{section.body_hi}</p>

                {section.eligibility_hi && section.eligibility_hi.length > 0 && (
                  <div className="mt-4">
                    <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-brand-700">
                      पात्रता मानदंड
                    </h3>
                    <ul className="space-y-1.5">
                      {section.eligibility_hi.map((item) => (
                        <li key={item} className="flex gap-2 text-sm text-ink-700">
                          <span aria-hidden="true" className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {section.documents_hi && section.documents_hi.length > 0 && (
                  <div className="mt-4">
                    <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-saffron-700">
                      ज़रूरी दस्तावेज़
                    </h3>
                    <ul className="space-y-1.5">
                      {section.documents_hi.map((item) => (
                        <li key={item} className="flex gap-2 text-sm text-ink-700">
                          <span aria-hidden="true">📄</span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="mt-4 text-[11px] text-ink-400">
                  स्रोत: {section.source}
                  {section.page ? ` · पृष्ठ ${section.page}` : ""}
                </p>
              </section>
            ))}
          </>
        )}
      </main>
    </div>
  );
}
