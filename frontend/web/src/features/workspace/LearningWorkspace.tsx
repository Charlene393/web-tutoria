import {
  BookOpen,
  Camera,
  CheckCircle2,
  Hand,
  Sparkle,
  Star,
  Trophy,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { AuthUser } from "../../api/kslClient";
import { PhotoExplainStudio } from "../photo/PhotoExplainStudio";
import { SignUploadStudio } from "../sign/SignUploadStudio";
import { SpeechToKslStudio, type ListenMapProgress } from "../speech/SpeechToKslStudio";

type WorkspaceSection = "listen-map" | "sign" | "photo";

type ModuleCard = {
  key: WorkspaceSection;
  title: string;
  icon: typeof BookOpen;
};

const MODULES: ModuleCard[] = [
  {
    key: "listen-map",
    title: "Listen and map",
    icon: BookOpen,
  },
  {
    key: "sign",
    title: "Check your sign",
    icon: Hand,
  },
  {
    key: "photo",
    title: "Explain from a photo",
    icon: Camera,
  },
];

const CHALLENGES = [
  {
    key: "capturedInput",
    unit: "Unit 1",
    title: "Catch a phrase",
    copy: "Record a phrase or type one manually to start the mapping flow.",
  },
  {
    key: "mappedGloss",
    unit: "Unit 2",
    title: "Map to gloss",
    copy: "Turn that phrase into a usable KSL gloss sequence from the backend.",
  },
  {
    key: "playedSequence",
    unit: "Unit 3",
    title: "Play the sequence",
    copy: "Run through the mapped stickman and avatar sequence to verify the reading.",
  },
  {
    key: "playedSpeech",
    unit: "Unit 4",
    title: "Speak it back",
    copy: "Generate audio feedback for the mapped phrase and complete the cycle.",
  },
] as const;

export function LearningWorkspace({
  user,
  onLogout,
}: {
  user: AuthUser;
  onLogout: () => void;
}) {
  const [section, setSection] = useState<WorkspaceSection>("listen-map");
  const [listenMapProgress, setListenMapProgress] = useState<ListenMapProgress>({
    capturedInput: false,
    mappedGloss: false,
    playedSequence: false,
    playedSpeech: false,
  });
  const [signCompleted, setSignCompleted] = useState(false);
  const [photoCompleted, setPhotoCompleted] = useState(false);

  const activeModule = MODULES.find((module) => module.key === section) ?? MODULES[0];
  const ActiveIcon = activeModule.icon;

  const listenMapCompletedCount = CHALLENGES.filter(
    (challenge) => listenMapProgress[challenge.key],
  ).length;
  const listenMapProgressPercent = Math.round(
    (listenMapCompletedCount / CHALLENGES.length) * 100,
  );
  const allListenMapComplete = listenMapCompletedCount === CHALLENGES.length;

  const moduleCompletionCount = [
    allListenMapComplete,
    signCompleted,
    photoCompleted,
  ].filter(Boolean).length;

  const topSummary = useMemo(() => {
    if (section === "listen-map") {
      return {
        title: "Listen and map",
        detail: `${listenMapCompletedCount}/${CHALLENGES.length} units completed`,
      };
    }

    if (section === "sign") {
      return {
        title: "Check your sign",
        detail: signCompleted ? "Module completed once" : "Ready for sign verification",
      };
    }

    return {
      title: "Explain from a photo",
      detail: photoCompleted ? "Module completed once" : "Ready for visual learning",
    };
  }, [listenMapCompletedCount, photoCompleted, section, signCompleted]);

  return (
    <main className="workspace-shell">
      <section className="workspace-hero ">
        <div className="workspace-hero-copy">
          <p className="workspace-kicker">Learning platform</p>
          <h1>Tutoria</h1>
          
        </div>

        <div className="workspace-hero-metrics">
          
          <div className="workspace-user-chip">
            
            <div>
              <strong>{user.full_name || user.email}</strong>
              <span>{user.email}</span>
            </div>
          </div>
          <button type="button" className="workspace-logout" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </section>

      <section className="module-section">
        <div className="journey-header">
          <div>
            <h2>Products</h2>
          </div>
        </div>

        <div className="module-grid">
          {MODULES.map((module) => {
            const ModuleIcon = module.icon;
            const isActive = section === module.key;
            const isComplete =
              module.key === "listen-map"
                ? allListenMapComplete
                : module.key === "sign"
                  ? signCompleted
                  : photoCompleted;

            return (
              <button
                key={module.key}
                type="button"
                className={[
                  "module-card",
                  isActive ? "is-active" : "",
                  isComplete ? "is-complete" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => setSection(module.key)}
              >
                <div className="module-card-icon item-center">
                  <ModuleIcon size={40} />
                  {isComplete ? <CheckCircle2 size={16} /> : null}
                </div>
                <strong><h2>{module.title}</h2></strong>
              </button>
            );
          })}
        </div>
      </section>

      {section === "listen-map" ? (
        <section className="listen-map-layout">
          <aside className="unit-ladder">

            <div className="xp-card">
              <div className="xp-ring">
                <div className="xp-ring-inner">
                  <strong>{listenMapProgressPercent}%</strong>
                </div>
              </div>
              <div className="xp-copy">
                <strong>Progress </strong>
                <p>Track your progress.</p>
              </div>
            </div>

            {allListenMapComplete ? (
              <div className="celebration-card">
                <div className="celebration-head">
                  <Trophy size={18} />
                  <strong>Sequence complete</strong>
                </div>
                <p>You completed the entire listen-and-map cycle. Try a new phrase or jump into a companion module.</p>
              </div>
            ) : null}
          </aside>

          <div className="listen-map-main">

            <section className="workspace-focus">

              <SpeechToKslStudio
                onLessonReady={() => undefined}
                onProgressChange={setListenMapProgress}
                onOpenSignStudio={() => setSection("sign")}
                onOpenPhotoStudio={() => setSection("photo")}
              />
            </section>
          </div>
        </section>
      ) : null}

      {section === "sign" ? (
        <section className="workspace-focus">
          <div className="workspace-focus-header">
            <div>
              <h2>Check your sign</h2>
            </div>
          </div>

          <SignUploadStudio
            onComplete={() => {
              setSignCompleted(true);
            }}
          />
        </section>
      ) : null}

      {section === "photo" ? (
        <section className="workspace-focus">
          <div className="workspace-focus-header">
            <div>
              <h2>Explain from a photo</h2>
            </div>
            
          </div>

          <PhotoExplainStudio
            onComplete={() => {
              setPhotoCompleted(true);
            }}
          />
        </section>
      ) : null}
    </main>
  );
}
