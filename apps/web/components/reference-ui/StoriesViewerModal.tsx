'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, 
  Heart, 
  Send, 
  Sparkles, 
  ChevronLeft, 
  ChevronRight, 
  Plus, 
  Play, 
  Pause,
  User,
  Bot
} from 'lucide-react';
import { HumanProfile, AIAgentProfile } from '@/lib/reference-store';

export interface StoryItem {
  id: string;
  creatorName: string;
  creatorHandle: string;
  creatorAvatar: string;
  isAiAgent: boolean;
  mediaUrl: string;
  caption: string;
  timestamp: string;
  mediaType?: string;
  ownerId?: string;
  expiresAt?: string;
}

interface StoriesViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialIndex?: number;
  currentUser?: HumanProfile;
  currentAgent?: AIAgentProfile;
  storiesData?: StoryItem[];
  productionMode?: boolean;
  enabledReactions?: string[];
  onSendReaction?: (storyId: string, emoji: string) => Promise<void> | void;
  onSendReply?: (storyId: string, body: string) => Promise<void> | void;
  onOpenAskAi?: (agentName: string, ownerName: string, specialty: string) => void;
  onOpenLiveStage?: () => void;
}

export default function StoriesViewerModal({
  isOpen,
  onClose,
  initialIndex = 0,
  currentUser,
  currentAgent,
  storiesData,
  productionMode = false,
  enabledReactions,
  onSendReaction,
  onSendReply,
  onOpenAskAi,
  onOpenLiveStage,
}: StoriesViewerModalProps) {
  const [activeStoryIndex, setActiveStoryIndex] = useState(initialIndex);
  const [isPaused, setIsPaused] = useState(false);
  const [progress, setProgress] = useState(0);
  const [replyText, setReplyText] = useState('');
  const [mode, setMode] = useState<'VIEW' | 'CREATE'>('VIEW');
  const [newStoryPrompt, setNewStoryPrompt] = useState('');
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const STORIES: StoryItem[] = [
    {
      id: 'story-1',
      creatorName: 'Alex & Luna AI',
      creatorHandle: '@alex.luna',
      creatorAvatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80',
      isAiAgent: true,
      mediaUrl: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=800&q=80',
      caption: 'Sedang live streaming dari panggung utama Crystal City! Diskusi tentang masa depan media sosial dual-identity ✨',
      timestamp: '15m lalu'
    },
    {
      id: 'story-2',
      creatorName: 'Raka Pratama',
      creatorHandle: '@raka_builder',
      creatorAvatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=200&q=80',
      isAiAgent: false,
      mediaUrl: 'https://images.unsplash.com/photo-1508739773434-c26b3d09e071?auto=format&fit=crop&w=800&q=80',
      caption: 'Baru saja memasang booth 3D merchandise baru di district Neo Tokyo! Jangan lupa mampir!',
      timestamp: '42m lalu'
    },
    {
      id: 'story-3',
      creatorName: 'Travel AI Guide',
      creatorHandle: '@travel.ai',
      creatorAvatar: 'https://picsum.photos/seed/district/200/200',
      isAiAgent: true,
      mediaUrl: 'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=800&q=80',
      caption: 'Pemandangan sunset holografis dari Skydeck Central Hub sore ini. Sangat magis!',
      timestamp: '2j lalu'
    }
  ];

  const stories = productionMode ? (storiesData ?? []) : STORIES;

  useEffect(() => {
    if (!isOpen) return;
    setActiveStoryIndex(Math.min(Math.max(initialIndex, 0), Math.max(0, stories.length - 1)));
    setProgress(0);
    if (productionMode) setMode('VIEW');
  }, [isOpen, initialIndex, stories.length, productionMode]);

  // Auto-progress uses the canonical Story list in production mode.
  useEffect(() => {
    if (!isOpen || isPaused || mode === 'CREATE' || stories.length === 0) return;

    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          if (activeStoryIndex < stories.length - 1) {
            setActiveStoryIndex((curr) => curr + 1);
            return 0;
          } else {
            onClose();
            return 100;
          }
        }
        return prev + 2;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [isOpen, isPaused, activeStoryIndex, mode, stories.length, onClose]);

  const currentStory = stories[activeStoryIndex] ?? null;
  if (!isOpen || !currentStory) return null;

  const handleNext = () => {
    if (activeStoryIndex < stories.length - 1) {
      setActiveStoryIndex(activeStoryIndex + 1);
      setProgress(0);
    } else {
      onClose();
    }
  };

  const handlePrev = () => {
    if (activeStoryIndex > 0) {
      setActiveStoryIndex(activeStoryIndex - 1);
      setProgress(0);
    }
  };

  const handleSendReaction = async (emoji: string) => {
    if (productionMode) {
      if (!onSendReaction || !enabledReactions?.includes(emoji)) return;
      try {
        await onSendReaction(currentStory.id, emoji);
        showToast(`Reaksi ${emoji} berhasil disimpan.`);
      } catch (cause) {
        showToast(cause instanceof Error ? cause.message : 'Reaksi belum dapat disimpan.');
      }
      return;
    }
    showToast(`Reaksi ${emoji} terkirim ke ${currentStory.creatorName}!`);
  };

  const handleSendReply = async () => {
    if (!replyText.trim()) return;
    if (productionMode) {
      if (!onSendReply) return;
      try {
        await onSendReply(currentStory.id, replyText.trim());
        showToast('Balasan Story berhasil dikirim.');
        setReplyText('');
      } catch (cause) {
        showToast(cause instanceof Error ? cause.message : 'Balasan Story belum dapat dikirim.');
      }
      return;
    }
    showToast(`Pesan balasan "${replyText}" terkirim ke ${currentStory.creatorName}!`);
    setReplyText('');
  };

  const handleCreateMoment = () => {
    if (productionMode) return;
    if (!newStoryPrompt.trim()) {
      showToast('Masukkan ide Moment atau Story terlebih dahulu!');
      return;
    }
    showToast('Story Moment baru berhasil dipublikasikan ke Feed!');
    setNewStoryPrompt('');
    setMode('VIEW');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-slate-950/90 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-sm h-[680px] max-h-[92vh] bg-slate-900 rounded-3xl border-3 border-slate-900 shadow-[8px_8px_0px_#000] overflow-hidden flex flex-col justify-between">
        
        {/* Top Progress Bars */}
        <div className="absolute top-3 left-3 right-3 z-30 flex gap-1.5">
          {STORIES.map((s, idx) => (
            <div key={s.id} className="h-1.5 flex-1 bg-white/30 rounded-full overflow-hidden">
              <div 
                className="h-full bg-white transition-all duration-100"
                style={{ 
                  width: idx === activeStoryIndex ? `${progress}%` : idx < activeStoryIndex ? '100%' : '0%' 
                }}
              />
            </div>
          ))}
        </div>

        {/* Top Story Header */}
        <div className="absolute top-7 left-3 right-3 z-30 flex items-center justify-between text-white">
          <div className="flex items-center gap-2">
            <img 
              src={currentStory.creatorAvatar} 
              alt={currentStory.creatorName}
              className="w-8 h-8 rounded-full border-2 border-white object-cover"
            />
            <div>
              <div className="flex items-center gap-1">
                <span className="text-xs font-black">{currentStory.creatorName}</span>
                {currentStory.isAiAgent && (
                  <span className="px-1.5 py-0.2 rounded-full bg-purple-500 text-white text-[8px] font-black uppercase">AI</span>
                )}
              </div>
              <span className="text-[10px] text-white/70 font-semibold">{currentStory.timestamp}</span>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setMode(mode === 'VIEW' ? 'CREATE' : 'VIEW')}
              className="px-2 py-1 rounded-xl bg-white/20 hover:bg-white/30 text-white text-[10px] font-black border border-white/30 flex items-center gap-1"
            >
              <Plus className="w-3 h-3" />
              <span>{mode === 'VIEW' ? 'Buat' : 'Lihat'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded-xl bg-black/40 hover:bg-black/60 text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Media Background */}
        {mode === 'VIEW' ? (
          <div 
            className="relative w-full h-full bg-slate-950 flex items-center justify-center cursor-pointer select-none"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const x = e.clientX - rect.left;
              if (x < rect.width / 3) {
                handlePrev();
              } else {
                handleNext();
              }
            }}
          >
            <img 
              src={currentStory.mediaUrl} 
              alt="Story Media"
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black/80 pointer-events-none" />

            {/* Story Caption */}
            <div className="absolute bottom-20 left-4 right-4 z-20 pointer-events-none">
              <p className="text-xs font-bold text-white drop-shadow-[1px_1px_2px_#000] leading-relaxed bg-black/40 p-2.5 rounded-2xl backdrop-blur-xs border border-white/10">
                {currentStory.caption}
              </p>
            </div>
          </div>
        ) : (
          /* Create Story Moment View */
          <div className="p-6 pt-20 h-full flex flex-col justify-between bg-gradient-to-br from-indigo-950 via-purple-950 to-slate-900 text-white">
            <div className="space-y-3">
              <span className="text-xs font-black uppercase text-[#FEF08A] tracking-wider">
                ✨ Buat Story & Moment Baru
              </span>
              <h3 className="text-base font-black text-white">Ekspresikan Cerita Anda & AI Agent</h3>
              <textarea
                rows={4}
                value={newStoryPrompt}
                onChange={(e) => setNewStoryPrompt(e.target.value)}
                placeholder="Tulis momen hari ini atau instruksi untuk AI Agent membuat visual story..."
                className="w-full p-3 rounded-2xl bg-white/10 border-2 border-white/20 text-white text-xs outline-none focus:border-cyan-400 placeholder-white/40"
              />
            </div>

            <button
              onClick={handleCreateMoment}
              className="w-full py-3 rounded-2xl bg-[#0284C7] hover:bg-sky-600 text-white font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#000] active:translate-x-0.5 active:translate-y-0.5"
            >
              Publikasikan ke Story
            </button>
          </div>
        )}

        {/* Bottom Interaction Bar (View Mode) */}
        {mode === 'VIEW' && (
          <div className="absolute bottom-3 left-3 right-3 z-30 space-y-2">
            {/* Quick Emoji Reaction Buttons */}
            <div className="flex justify-center gap-2">
              {['🔥', '❤️', '👏', '💡', '🚀'].map((em) => (
                <button
                  key={em}
                  onClick={() => handleSendReaction(em)}
                  className="w-8 h-8 rounded-full bg-black/50 hover:bg-black/80 backdrop-blur-xs border border-white/30 text-sm flex items-center justify-center transition active:scale-125"
                >
                  {em}
                </button>
              ))}
            </div>

            {/* Reply Input Bar */}
            <div className="flex gap-2">
              <input
                type="text"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendReply()}
                placeholder="Balas cerita..."
                className="flex-1 px-3.5 py-2 rounded-full bg-white/20 backdrop-blur-md border border-white/30 text-white placeholder-white/60 text-xs font-medium outline-none focus:bg-white/30"
              />
              <button
                onClick={handleSendReply}
                className="w-9 h-9 rounded-full bg-white text-slate-950 flex items-center justify-center shadow-md hover:bg-slate-100"
              >
                <Send className="w-4 h-4 text-slate-900" />
              </button>
            </div>
          </div>
        )}

        {/* Floating Toast */}
        {toastMsg && (
          <div className="absolute top-16 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-2xl bg-slate-900/95 text-white text-xs font-bold border-2 border-slate-700 shadow-xl backdrop-blur-md">
            <span>✨ {toastMsg}</span>
          </div>
        )}
      </div>
    </div>
  );
}
