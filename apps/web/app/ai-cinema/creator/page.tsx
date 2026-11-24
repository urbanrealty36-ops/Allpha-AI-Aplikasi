"use client";

import AiCinemaCreatorWorkspace from "../../../components/ai-cinema/AiCinemaCreatorWorkspace";

export default function AiCinemaCreatorPage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-700">AI Cinema · Production</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 dark:text-white sm:text-3xl">Creator Studio</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">Ruang produksi eksklusif untuk kreator, sutradara, dan pemilik konten. Kelola proyek, media, episode, kolaborator, dan proses produksi melalui layanan backend Allpha.</p>
        </div>
        <a href="/ai-cinema" className="inline-flex items-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800">Kembali ke katalog film</a>
      </header>
      <AiCinemaCreatorWorkspace />
    </main>
  );
}
