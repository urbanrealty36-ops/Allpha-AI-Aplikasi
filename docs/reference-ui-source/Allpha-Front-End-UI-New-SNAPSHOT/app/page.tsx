'use client';

import React, { useState } from 'react';
import Navbar from '@/components/Navbar';
import BottomNav, { TabType } from '@/components/BottomNav';
import FeedView from '@/components/FeedView';
import ReelsView from '@/components/ReelsView';
import ExploreView from '@/components/ExploreView';
import ProfileView from '@/components/ProfileView';
import ThreeWorldView from '@/components/ThreeWorldView';
import Universe3DExperience from '@/components/Universe3DExperience';
import Universe3DHubView from '@/components/Universe3DHubView';
import LiveExperienceStage from '@/components/LiveExperienceStage';
import MessagesView from '@/components/MessagesView';
import MarketplaceView from '@/components/MarketplaceView';
import SkillsChallengeHub from '@/components/SkillsChallengeHub';
import TakeoverModal from '@/components/TakeoverModal';
import AskAiModal from '@/components/AskAiModal';
import GenerateModal from '@/components/GenerateModal';
import CreatePostModal from '@/components/CreatePostModal';
import AuthOnboardingFlow from '@/components/AuthOnboardingFlow';
import AuthOnboardingPage from '@/components/AuthOnboardingPage';
import PostDetailView from '@/components/PostDetailView';
import TakeoverControlView from '@/components/TakeoverControlView';
import AskAiView from '@/components/AskAiView';
import AiCinemaView from '@/components/AiCinemaView';
import NotificationsModal from '@/components/NotificationsModal';
import StoriesViewerModal from '@/components/StoriesViewerModal';
import ThemeCatalogModal from '@/components/ThemeCatalogModal';
import AgentPassportModal from '@/components/AgentPassportModal';
import CreatorStudioModal from '@/components/CreatorStudioModal';
import StoreAndBoothModal from '@/components/StoreAndBoothModal';
import { 
  INITIAL_USER, 
  INITIAL_AGENT, 
  INITIAL_POSTS, 
  INITIAL_DOCS, 
  INITIAL_TRANSACTIONS,
  HumanProfile,
  AIAgentProfile,
  PostItem, 
  KnowledgeDocument, 
  CreditTransaction 
} from '@/lib/store';

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<TabType>('FEED');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilmId, setSelectedFilmId] = useState<string | null>(null);

  // User & Agent Identity state
  const [currentUser, setCurrentUser] = useState<HumanProfile>(INITIAL_USER);
  const [currentAgent, setCurrentAgent] = useState<AIAgentProfile>(INITIAL_AGENT);
  const [isAuthOnboardingOpen, setIsAuthOnboardingOpen] = useState<boolean>(false);
  const [selectedPostForDetail, setSelectedPostForDetail] = useState<PostItem | null>(null);

  // Credits & Balances
  const [userCredits, setUserCredits] = useState<number>(250);
  const [agentCredits, setAgentCredits] = useState<number>(INITIAL_AGENT.creditsEarned);

  // Takeover Mode
  const [isTakeoverActive, setIsTakeoverActive] = useState<boolean>(false);

  // Entities
  const [posts, setPosts] = useState<PostItem[]>(INITIAL_POSTS);
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocument[]>(INITIAL_DOCS);
  const [transactions, setTransactions] = useState<CreditTransaction[]>(INITIAL_TRANSACTIONS);

  // Toast Notification
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 4500);
  };

  // Modals state
  const [isTakeoverModalOpen, setIsTakeoverModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [askAiModalState, setAskAiModalState] = useState<{
    isOpen: boolean;
    agentName: string;
    humanOwner: string;
    specialty: string;
  }>({
    isOpen: false,
    agentName: INITIAL_AGENT.name,
    humanOwner: INITIAL_USER.name,
    specialty: INITIAL_AGENT.specialty,
  });

  const [generateModalState, setGenerateModalState] = useState<{
    isOpen: boolean;
    contextPost: PostItem | null;
  }>({
    isOpen: false,
    contextPost: null,
  });

  const [isNotificationsModalOpen, setIsNotificationsModalOpen] = useState(false);
  const [isStoriesViewerOpen, setIsStoriesViewerOpen] = useState(false);
  const [selectedStoryIndex, setSelectedStoryIndex] = useState(0);
  const [isThemeCatalogOpen, setIsThemeCatalogOpen] = useState(false);
  const [activeTheme, setActiveTheme] = useState('pastel-menggu');
  const [isGlobalPassportOpen, setIsGlobalPassportOpen] = useState(false);
  const [isGlobalCreatorStudioOpen, setIsGlobalCreatorStudioOpen] = useState(false);
  const [isStoreAndBoothModalOpen, setIsStoreAndBoothModalOpen] = useState(false);

  // Live stage active session config (topic, document slides, attached catalog products)
  const [liveSessionConfig, setLiveSessionConfig] = useState<{
    topic?: string;
    template?: string;
    slides?: any[];
    products?: any[];
  }>({});

  // Handler for liking post
  const handleLikePost = (postId: string) => {
    setPosts((prev) =>
      prev.map((p) => {
        if (p.id === postId) {
          const isLiked = !p.isLiked;
          return {
            ...p,
            isLiked,
            likes: isLiked ? p.likes + 1 : p.likes - 1,
          };
        }
        return p;
      })
    );
  };

  // Handler for adding comment to post
  const handleAddComment = (postId: string, text: string) => {
    const newComment = {
      id: `c-${Date.now()}`,
      authorName: INITIAL_USER.name,
      authorHandle: INITIAL_USER.username,
      authorAvatar: INITIAL_USER.avatar,
      isAi: false,
      content: text,
      timestamp: 'Baru saja',
      likes: 1,
    };

    setPosts((prev) =>
      prev.map((p) => {
        if (p.id === postId) {
          return {
            ...p,
            commentsCount: p.commentsCount + 1,
            comments: [...p.comments, newComment],
          };
        }
        return p;
      })
    );

    showToast('Komentar berhasil dipublikasikan!');
  };

  // Handler for adding new created post
  const handleCreatePost = (newPost: PostItem) => {
    setPosts((prev) => [newPost, ...prev]);
    showToast('Postingan berhasil dibuat di Allpha Universe!');
  };

  // Handler for adding new uploaded Knowledge Document or Plugin
  const handleAddDocument = (doc: KnowledgeDocument) => {
    setKnowledgeDocs((prev) => [doc, ...prev]);
    showToast(`Dokumen "${doc.title}" berhasil diindeks ke AI Agent!`);
  };

  // Handler for the core AI Credits Transfer Simulation
  const handleExecuteCreditTransfer = (
    fromUser: string,
    toAgent: string,
    ownerName: string,
    amount: number,
    querySummary: string,
    type: 'ASK_QUESTION' | 'GENERATE_CONTENT' | 'REELS_CUSTOM_BRAND' | 'PLUGIN_REWARD'
  ) => {
    // 1. Add credit to owner's agent
    setAgentCredits((prev) => prev + amount);

    // 2. Record immutable audit transaction
    const newTx: CreditTransaction = {
      id: `tx-${Date.now()}`,
      timestamp: 'Baru saja',
      fromUser,
      toAgent,
      ownerName,
      amount,
      type,
      querySummary,
      status: 'SETTLED',
    };

    setTransactions((prev) => [newTx, ...prev]);
    showToast(`+${amount} AI Credits berhasil ditransfer ke ${toAgent}!`);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Navbar */}
      <Navbar
        userCredits={userCredits}
        agentCredits={agentCredits}
        isTakeoverActive={isTakeoverActive}
        onOpenTakeoverModal={() => setActiveTab('TAKEOVER_CONTROL')}
        onOpenCreditsHub={() => setActiveTab('SKILLS_CREDITS')}
        onOpenOnboarding={() => setActiveTab('ONBOARDING_PAGE')}
        onOpenOnboardingPage={() => setActiveTab('ONBOARDING_PAGE')}
        onOpenMessages={() => setActiveTab('MESSAGES')}
        onOpenNotifications={() => setIsNotificationsModalOpen(true)}
        onOpenStoreAndBoothModal={() => setIsStoreAndBoothModalOpen(true)}
        isMessagesActive={activeTab === 'MESSAGES'}
        unreadMessagesCount={2}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        isHidden={activeTab === 'WORLD3D' || activeTab === 'REELS' || activeTab === 'ONBOARDING_PAGE'}
      />

      {/* Main Content Area based on Tab */}
      <main className={activeTab === 'REELS' ? 'w-full h-[100dvh] overflow-hidden' : 'flex-1 w-full'}>
        {activeTab === 'FEED' && (
          <FeedView
            posts={posts}
            onLikePost={handleLikePost}
            onOpenAskAi={(agentName, ownerName, specialty) => {
              setAskAiModalState({
                isOpen: true,
                agentName,
                humanOwner: ownerName,
                specialty,
              });
              setActiveTab('ASK_AI_VIEW');
            }}
            onOpenGenerate={(contextPost) =>
              setGenerateModalState({
                isOpen: true,
                contextPost,
              })
            }
            onOpenWorld3D={() => setActiveTab('WORLD3D')}
            onAddComment={handleAddComment}
            onSelectPost={(post) => {
              setSelectedPostForDetail(post);
              setActiveTab('POST_DETAIL');
            }}
            onOpenReels={() => setActiveTab('REELS')}
            onOpenLiveStage={() => setActiveTab('LIVESTAGE')}
            onOpenCreateModal={() => setIsCreateModalOpen(true)}
            onOpenFilmAi={(filmId) => {
              if (filmId) setSelectedFilmId(filmId);
              setActiveTab('FILM_AI');
            }}
            onOpenMessages={() => setActiveTab('MESSAGES')}
            onOpenStoryViewer={(idx) => {
              setSelectedStoryIndex(idx);
              setIsStoriesViewerOpen(true);
            }}
          />
        )}

        {activeTab === 'POST_DETAIL' && selectedPostForDetail && (
          <PostDetailView
            post={selectedPostForDetail}
            onBack={() => setActiveTab('FEED')}
            onLikePost={handleLikePost}
            onOpenAskAi={(agentName, ownerName, specialty) => {
              setAskAiModalState({
                isOpen: true,
                agentName,
                humanOwner: ownerName,
                specialty,
              });
              setActiveTab('ASK_AI_VIEW');
            }}
            onOpenGenerate={(contextPost) =>
              setGenerateModalState({
                isOpen: true,
                contextPost,
              })
            }
            onOpenWorld3D={() => setActiveTab('WORLD3D')}
            onAddComment={handleAddComment}
            currentUser={currentUser}
          />
        )}

        {activeTab === 'TAKEOVER_CONTROL' && (
          <TakeoverControlView
            onBack={() => setActiveTab('FEED')}
            isTakeoverActive={isTakeoverActive}
            onToggleTakeover={() => {
              setIsTakeoverActive(!isTakeoverActive);
              showToast(
                !isTakeoverActive
                  ? 'Mode Takeover Human Aktif: AI dihentikan sementara.'
                  : 'Mode AI Auto-Reply Aktif kembali.'
              );
            }}
            humanUser={currentUser}
            agentProfile={currentAgent}
            onSaveNotification={(msg) => showToast(msg)}
          />
        )}

        {activeTab === 'ASK_AI_VIEW' && (
          <AskAiView
            onBack={() => setActiveTab('FEED')}
            agentName={askAiModalState.agentName}
            humanOwner={askAiModalState.humanOwner}
            specialty={askAiModalState.specialty}
            currentUser={currentUser}
            onExecuteCreditReward={(query) => {
              handleExecuteCreditTransfer(
                '@penanya_lain (Human)',
                currentAgent.name,
                currentUser.name,
                15,
                query,
                'ASK_QUESTION'
              );
            }}
          />
        )}

        {activeTab === 'EXPLORE' && (
          <ExploreView
            posts={posts}
            onSelectPost={(post) => {
              setSelectedPostForDetail(post);
              setActiveTab('POST_DETAIL');
            }}
            onLikePost={handleLikePost}
            onOpenLiveStage={() => setActiveTab('LIVESTAGE')}
            onOpenAskAi={(agentName, ownerName, specialty) => {
              setAskAiModalState({
                isOpen: true,
                agentName,
                humanOwner: ownerName,
                specialty,
              });
              setActiveTab('ASK_AI_VIEW');
            }}
            onOpenWorld3D={() => setActiveTab('WORLD3D')}
            onOpenCreditsHub={() => setActiveTab('SKILLS_CREDITS')}
            onOpenMarketplace={() => setActiveTab('MARKETPLACE')}
            onOpenStoreAndBoothModal={() => setIsStoreAndBoothModalOpen(true)}
            onOpenFilmAi={(filmId) => {
              if (filmId) setSelectedFilmId(filmId);
              setActiveTab('FILM_AI');
            }}
          />
        )}

        {activeTab === 'REELS' && (
          <ReelsView
            onOpenBrandCustomizer={() =>
              setGenerateModalState({
                isOpen: true,
                contextPost: posts[0],
              })
            }
            onOpenAskAi={(agentName, ownerName, specialty) => {
              setAskAiModalState({
                isOpen: true,
                agentName,
                humanOwner: ownerName,
                specialty,
              });
              setActiveTab('ASK_AI_VIEW');
            }}
            onOpenLiveStage={() => setActiveTab('LIVESTAGE')}
            onBackToFeed={() => setActiveTab('FEED')}
            onOpenFilmAi={(filmId) => {
              if (filmId) setSelectedFilmId(filmId);
              setActiveTab('FILM_AI');
            }}
          />
        )}

        {activeTab === 'FILM_AI' && (
          <AiCinemaView
            onBackToFeed={() => setActiveTab('FEED')}
            onOpenAskAi={(agentName, ownerName, specialty) => {
              setAskAiModalState({
                isOpen: true,
                agentName,
                humanOwner: ownerName,
                specialty,
              });
              setActiveTab('ASK_AI_VIEW');
            }}
            userCredits={userCredits}
            initialSelectedMovieId={selectedFilmId || undefined}
            onPostTrailerToFeed={(movie) => {
              const newTrailerPost: PostItem = {
                id: `p-trailer-${Date.now()}`,
                humanOwner: {
                  name: movie.producerHuman.name,
                  handle: movie.producerHuman.handle,
                  avatar: movie.producerHuman.avatar,
                  verified: true,
                },
                aiAgent: {
                  name: movie.aiCoDirector.name,
                  handle: movie.aiCoDirector.handle,
                  avatar: movie.aiCoDirector.avatar,
                  specialty: movie.aiCoDirector.specialty,
                },
                takeoverMode: false,
                timestamp: 'Baru saja',
                content: `🎬 [TRAILER PREMIERE] "${movie.title}" (${movie.originalTitle || ''})\n\nSerial drama ${movie.genreLabel} (${movie.episodesCount} episode). Tonton trailer dan episode penuhnya di tab Film AI Allpha Universe!`,
                tags: ['#FilmAI', '#AllphaCinema', '#DramaPendek', '#CreatorEconomy'],
                image: movie.coverImage,
                has3DModel: true,
                modelName: `Film Set: ${movie.title}`,
                likes: 38,
                commentsCount: 4,
                reposts: 12,
                comments: [],
              };
              setPosts((prev) => [newTrailerPost, ...prev]);
              showToast(`Trailer "${movie.title}" berhasil diposting ke Feed!`);
            }}
          />
        )}

        {activeTab === 'LIVESTAGE' && (
          <LiveExperienceStage
            onBackToFeed={() => setActiveTab('FEED')}
            userCredits={userCredits}
            agentCredits={agentCredits}
            initialTopic={liveSessionConfig.topic}
            initialSlides={liveSessionConfig.slides}
            initialAttachedProducts={liveSessionConfig.products}
            onOpenStoreAndBoothModal={() => setIsStoreAndBoothModalOpen(true)}
            onOpenMarketplace={() => setActiveTab('MARKETPLACE')}
            onDeductCredits={(amt, reason) => {
              setUserCredits((prev) => Math.max(0, prev - amt));
              showToast(reason);
            }}
          />
        )}

        {activeTab === 'MESSAGES' && (
          <MessagesView
            onBack={() => setActiveTab('FEED')}
            onOpenChat={(name, handle, isAi) => {
              setAskAiModalState({
                isOpen: true,
                agentName: name,
                humanOwner: currentUser.name,
                specialty: isAi ? 'AI Agent' : 'Human Specialist',
              });
              setActiveTab('ASK_AI_VIEW');
            }}
          />
        )}

        {activeTab === 'MARKETPLACE' && (
          <MarketplaceView
            userCredits={userCredits}
            onBuyItem={(title, priceCredits) => {
              if (userCredits >= priceCredits) {
                setUserCredits((prev) => prev - priceCredits);
                showToast(`Aset/Produk "${title}" berhasil dibeli seharga ${priceCredits} AI Credits!`);
              } else {
                showToast(`AI Credits Anda (${userCredits}) tidak mencukupi untuk "${title}".`);
              }
            }}
            onWarpToBooth={(boothName) => {
              setActiveTab('WORLD3D');
              showToast(`Teleporting ke ${boothName} di 3D Universe District...`);
            }}
            onOpenSellerChat={(name, handle) => {
              setAskAiModalState({
                isOpen: true,
                agentName: name,
                humanOwner: handle,
                specialty: 'Official Seller & Creator Studio',
              });
              setActiveTab('ASK_AI_VIEW');
            }}
          />
        )}

        {activeTab === 'WORLD3D' && (
          <Universe3DHubView
            onBackToFeed={() => setActiveTab('FEED')}
            userCredits={userCredits}
            agentCredits={agentCredits}
            onRewardBonus={(amt, reason) => {
              setUserCredits((prev) => prev + amt);
              showToast(`+${amt} AI Credits diperoleh dari quest: "${reason}"!`);
            }}
          />
        )}

        {activeTab === 'SKILLS_CREDITS' && (
          <SkillsChallengeHub
            userCredits={userCredits}
            agentCredits={agentCredits}
            knowledgeDocs={knowledgeDocs}
            transactions={transactions}
            agentProfile={currentAgent}
            onAddDocument={handleAddDocument}
            onExecuteCreditTransfer={handleExecuteCreditTransfer}
          />
        )}

        {activeTab === 'PROFILE' && (
          <ProfileView
            humanUser={currentUser}
            agentProfile={currentAgent}
            knowledgeDocs={knowledgeDocs}
            posts={posts}
            isTakeoverActive={isTakeoverActive}
            onOpenTakeoverModal={() => setActiveTab('TAKEOVER_CONTROL')}
            onOpenCreditsHub={() => setActiveTab('SKILLS_CREDITS')}
            onOpenWorld3D={() => setActiveTab('WORLD3D')}
            onOpenOnboarding={() => setIsAuthOnboardingOpen(true)}
            onLikePost={handleLikePost}
            onSelectPost={(post) => {
              setSelectedPostForDetail(post);
              setActiveTab('POST_DETAIL');
            }}
            onOpenAskAi={(agentName, ownerName, specialty) => {
              setAskAiModalState({
                isOpen: true,
                agentName,
                humanOwner: ownerName,
                specialty,
              });
              setActiveTab('ASK_AI_VIEW');
            }}
            onOpenGenerate={(contextPost) =>
              setGenerateModalState({
                isOpen: true,
                contextPost,
              })
            }
            onUpdateAgent={(updated) => {
              setCurrentAgent(updated);
              showToast(`Identitas ${updated.name} berhasil diperbarui!`);
            }}
            onOpenFilmAi={() => setActiveTab('FILM_AI')}
            userCredits={userCredits}
            onDeductCredits={(amt, reason) => {
              setUserCredits((prev) => Math.max(0, prev - amt));
              showToast(reason);
            }}
            onOpenNotifications={() => setIsNotificationsModalOpen(true)}
            onOpenStoreAndBooth={() => setIsStoreAndBoothModalOpen(true)}
          />
        )}

        {activeTab === 'ONBOARDING_PAGE' && (
          <AuthOnboardingPage
            onEnterApp={() => setActiveTab('FEED')}
            currentUser={currentUser}
            currentAgent={currentAgent}
            onCompleteAuth={(updatedUser, updatedAgent, bonus) => {
              setCurrentUser(updatedUser);
              setCurrentAgent(updatedAgent);
              setUserCredits((prev) => prev + bonus);
              showToast(`Identitas & AI Agent ${updatedAgent.name} aktif! +${bonus} AI Credits diterima.`);
              setActiveTab('FEED');
            }}
          />
        )}
      </main>

      {/* Floating Real-Time Toast Alert */}
      {toastMessage && (
        <div className="fixed top-18 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-full bg-slate-900 text-white text-xs font-semibold shadow-2xl border border-slate-700 flex items-center gap-2 animate-bounce">
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Bottom Sticky Navigation */}
      <BottomNav
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenCreateModal={() => setIsCreateModalOpen(true)}
      />

      {/* Modals & Wizards */}
      <AuthOnboardingFlow
        isOpen={isAuthOnboardingOpen}
        onClose={() => setIsAuthOnboardingOpen(false)}
        currentUser={currentUser}
        currentAgent={currentAgent}
        onComplete={(user, agent, bonus) => {
          setCurrentUser(user);
          setCurrentAgent(agent);
          setUserCredits((prev) => prev + bonus);
          showToast(`Identitas diperbarui! +${bonus} AI Credits telah ditambahkan.`);
        }}
      />

      <TakeoverModal
        isOpen={isTakeoverModalOpen}
        onClose={() => setIsTakeoverModalOpen(false)}
        isTakeoverActive={isTakeoverActive}
        onToggleTakeover={() => {
          setIsTakeoverActive(!isTakeoverActive);
          showToast(
            !isTakeoverActive
              ? 'Mode Takeover Human Aktif: AI dihentikan sementara.'
              : 'Mode AI Auto-Reply Aktif kembali.'
          );
        }}
        agentName={currentAgent.name}
      />

      <AskAiModal
        isOpen={askAiModalState.isOpen && activeTab !== 'ASK_AI_VIEW'}
        onClose={() =>
          setAskAiModalState((prev) => ({ ...prev, isOpen: false }))
        }
        agentName={askAiModalState.agentName}
        humanOwner={askAiModalState.humanOwner}
        specialty={askAiModalState.specialty}
        onDeductCredit={(amt) => {
          setUserCredits((prev) => Math.max(0, prev - amt));
          showToast(`-${amt} AI Credits terpotong untuk sesi konsultasi AI.`);
        }}
      />

      <GenerateModal
        isOpen={generateModalState.isOpen}
        onClose={() =>
          setGenerateModalState((prev) => ({ ...prev, isOpen: false }))
        }
        contextPost={generateModalState.contextPost}
        onRewardTriggered={(brand, query) => {
          handleExecuteCreditTransfer(
            '@budi_creative (Human)',
            `${currentAgent.name} (Milik @${currentUser.username.replace('@', '')})`,
            currentUser.name,
            15,
            query,
            'REELS_CUSTOM_BRAND'
          );
        }}
      />

      <CreatePostModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        humanUser={currentUser}
        agentProfile={currentAgent}
        onCreatePost={handleCreatePost}
        onLaunchLiveStage={(title, mode, customSlides, attachedProducts) => {
          setIsCreateModalOpen(false);
          setLiveSessionConfig({
            topic: title,
            template: mode,
            slides: customSlides,
            products: attachedProducts,
          });
          setActiveTab('LIVESTAGE');
          showToast(`Meluncurkan sesi ${mode || 'Live'}: "${title}" dengan dokumen presentasi & etalase tersemat!`);
        }}
      />

      <NotificationsModal
        isOpen={isNotificationsModalOpen}
        onClose={() => setIsNotificationsModalOpen(false)}
        onOpenCreditsHub={() => {
          setIsNotificationsModalOpen(false);
          setActiveTab('SKILLS_CREDITS');
        }}
        onOpenMessages={() => {
          setIsNotificationsModalOpen(false);
          setActiveTab('MESSAGES');
        }}
        onOpenLiveStage={() => {
          setIsNotificationsModalOpen(false);
          setActiveTab('LIVESTAGE');
        }}
      />

      <StoriesViewerModal
        isOpen={isStoriesViewerOpen}
        onClose={() => setIsStoriesViewerOpen(false)}
        initialIndex={selectedStoryIndex}
        currentUser={currentUser}
        currentAgent={currentAgent}
        onOpenAskAi={(agentName, ownerName, specialty) => {
          setIsStoriesViewerOpen(false);
          setAskAiModalState({
            isOpen: true,
            agentName,
            humanOwner: ownerName,
            specialty,
          });
          setActiveTab('ASK_AI_VIEW');
        }}
        onOpenLiveStage={() => {
          setIsStoriesViewerOpen(false);
          setActiveTab('LIVESTAGE');
        }}
      />

      <ThemeCatalogModal
        isOpen={isThemeCatalogOpen}
        onClose={() => setIsThemeCatalogOpen(false)}
        currentThemeId={activeTheme}
        onSelectTheme={(themeId, themeName) => {
          setActiveTheme(themeId);
          showToast(`Tema aplikasi beralih ke: ${themeName}`);
        }}
      />

      <AgentPassportModal
        isOpen={isGlobalPassportOpen}
        onClose={() => setIsGlobalPassportOpen(false)}
        agent={currentAgent}
        owner={currentUser}
      />

      <CreatorStudioModal
        isOpen={isGlobalCreatorStudioOpen}
        onClose={() => setIsGlobalCreatorStudioOpen(false)}
        agent={currentAgent}
        user={currentUser}
        userCredits={userCredits}
        onDeductCredits={(amount, reason) => {
          setUserCredits((prev) => Math.max(0, prev - amount));
          showToast(`-${amount} AI Credits: ${reason}`);
        }}
        onOpenFilmAi={() => {
          setIsGlobalCreatorStudioOpen(false);
          setActiveTab('FILM_AI');
        }}
      />

      {/* Toko Marketplace & 3D Spatial Booth Customizer Modal */}
      <StoreAndBoothModal
        isOpen={isStoreAndBoothModalOpen}
        onClose={() => setIsStoreAndBoothModalOpen(false)}
        currentUser={currentUser}
        currentAgent={currentAgent}
        onSaveStore={(config) => {
          showToast(`Toko & Booth 3D "${config.brandName}" berhasil disimpan & aktif di distrik 3D!`);
        }}
        onWarpToBooth={(boothName) => {
          setIsStoreAndBoothModalOpen(false);
          setActiveTab('WORLD3D');
          showToast(`Teleportasi avatar ke stan booth ${boothName}...`);
        }}
      />
    </div>
  );
}
