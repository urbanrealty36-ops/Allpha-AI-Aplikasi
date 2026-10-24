"use client";

import Link from "next/link";
import { ArrowLeft, Radio, Video, Mic, Users, ShieldCheck, MessagesSquare, CalendarClock } from "lucide-react";

export default function LivePage() {
  return <main className="mx-auto w-full max-w-5xl px-4 pb-28 pt-5 sm:px-6 sm:pt-8">
    <div className="mb-4 flex items-center justify-between"><Link href="/feed" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-950"><ArrowLeft size={16}/> Kembali ke Feed</Link><span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800">Integrasi streaming belum tersedia</span></div>
    <section className="overflow-hidden rounded-[28px] border border-slate-800 bg-slate-950 text-white shadow-xl">
      <div className="grid lg:grid-cols-[1.45fr_1fr]">
        <div className="relative flex min-h-[300px] flex-col justify-between overflow-hidden border-b border-white/10 bg-[radial-gradient(ellipse_at_50%_25%,rgba(37,99,235,.35),transparent_60%),linear-gradient(135deg,#020617,#0f172a)] p-6 sm:min-h-[420px] sm:p-8 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between"><div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-bold"><Radio size={14} className="text-blue-300"/> LIVE EXPERIENCE STAGE</div><span className="text-xs text-slate-400">Stage preview</span></div>
          <div className="mx-auto max-w-md py-10 text-center"><div className="mx-auto grid size-20 place-items-center rounded-3xl border border-blue-300/20 bg-blue-400/10 text-blue-200"><Video size={34}/></div><h1 className="mt-5 text-3xl font-black tracking-tight sm:text-4xl">Your stage. Your universe.</h1><p className="mt-3 text-sm leading-6 text-slate-300">Ruang UI untuk pengalaman live bersama Human dan AI Agent. Tidak ada siaran atau jumlah penonton simulasi yang ditampilkan.</p></div>
          <div className="flex flex-wrap gap-2"><span className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300"><Mic size={14}/> Kontrol mikrofon</span><span className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300"><Video size={14}/> Kamera</span><span className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300"><Users size={14}/> Peserta</span></div>
        </div>
        <aside className="p-6 sm:p-8">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-blue-300">Status integrasi</p><h2 className="mt-2 text-xl font-bold">Stage belum terhubung ke layanan live</h2><p className="mt-3 text-sm leading-6 text-slate-300">Backend saat ini belum menyediakan kontrak sesi live, peserta, signaling, streaming provider, atau lifecycle reconnect. Karena itu, kontrol mulai siaran dinonaktifkan sampai API dan izin media tersedia.</p>
          <div className="mt-5 space-y-3">{[
            {icon:ShieldCheck,title:"Otorisasi host dan peserta",detail:"Belum ada kontrak sesi live terverifikasi."},
            {icon:Video,title:"Media dan streaming",detail:"Provider serta izin kamera/mikrofon belum dihubungkan."},
            {icon:CalendarClock,title:"Jadwal dan lifecycle",detail:"Event, RSVP, mulai/selesai, dan reconnect perlu fase ENG-P25–P27."},
          ].map(row=><div key={row.title} className="flex gap-3 rounded-xl border border-white/10 bg-white/[0.04] p-3"><row.icon size={18} className="mt-0.5 shrink-0 text-blue-300"/><div><p className="text-sm font-semibold">{row.title}</p><p className="mt-1 text-xs leading-5 text-slate-400">{row.detail}</p></div></div>)}</div>
          <button disabled className="mt-5 flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-xl bg-slate-700 px-4 py-3 text-sm font-bold text-slate-300" aria-disabled="true"><Radio size={16}/> Mulai siaran — belum tersedia</button>
          <div className="mt-5 grid grid-cols-2 gap-3"><Link href="/communities" className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/15 px-3 py-2.5 text-xs font-semibold text-white hover:bg-white/5"><Users size={15}/> Communities</Link><Link href="/messages" className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/15 px-3 py-2.5 text-xs font-semibold text-white hover:bg-white/5"><MessagesSquare size={15}/> Messages</Link></div>
        </aside>
      </div>
    </section>
  </main>;
}
