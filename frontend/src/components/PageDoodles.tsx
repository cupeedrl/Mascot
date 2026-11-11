import {
  Compass,
  Hand,
  Heart,
  Lightbulb,
  Mail,
  MapPin,
  Medal,
  Paperclip,
  PencilLine,
  RefreshCw,
  Send,
  Sparkles,
  Star,
  Target,
  Trophy,
  Zap,
} from "lucide-react";

import { PenguinMark } from "./PenguinMark";

export type DoodleVariant = "learn" | "vocabulary" | "review" | "practice" | "about";

/**
 * Friendly, page-specific decoration for page headers. Each page has its own
 * theme on top of its existing background and accent colour:
 * - learn: exploring (dashed route, paper plane, compass, map pin)
 * - vocabulary: stationery (sticky notes, washi tape, pencil, paperclip)
 * - review: remembering (glowing bulb, flipping mini flashcards, refresh ring)
 * - practice: playing (trophy, target, medal, lightning, confetti)
 * - about: saying hello (waving hand, balloons, hearts, envelope)
 * Purely decorative (aria-hidden) and kept to the header's edges.
 */
export function PageDoodles({ variant, languageCode }: { variant: DoodleVariant; languageCode?: string }) {
  const zh = languageCode === "zh";
  return (
    <div className={`page-doodles page-doodles-${variant}`} aria-hidden="true">
      {variant === "learn" && (
        <>
          <svg className="pd-route" viewBox="0 0 240 70" preserveAspectRatio="none">
            <path d="M4 60 C 60 10, 120 70, 236 12" />
          </svg>
          <Send className="pd pd-plane" size={22} />
          <Compass className="pd pd-compass" size={24} />
          <MapPin className="pd pd-pin" size={20} />
          <Star className="pd pd-star" size={16} />
          <span className="pd-bubble pd-bubble-hello" lang={languageCode}>{zh ? "你好!" : "Hello!"}</span>
        </>
      )}

      {variant === "vocabulary" && (
        <>
          <span className="pd-tape" />
          <span className="pd-note pd-note-a" lang={languageCode}>{zh ? "字" : "Aa"}</span>
          <span className="pd-note pd-note-b" lang={languageCode}>{zh ? "词" : "Bb"}</span>
          <span className="pd-note pd-note-c">♥</span>
          <PencilLine className="pd pd-pencil" size={22} />
          <Paperclip className="pd pd-clip" size={22} />
        </>
      )}

      {variant === "review" && (
        <>
          <span className="pd-glow" />
          <Lightbulb className="pd pd-bulb" size={26} />
          <span className="pd-flip pd-flip-a"><i>{zh ? "记" : "A"}</i><i>✓</i></span>
          <span className="pd-flip pd-flip-b"><i>{zh ? "忆" : "Z"}</i><i>✓</i></span>
          <span className="pd-ring"><RefreshCw size={16} /></span>
          <Sparkles className="pd pd-sparkle" size={18} />
          <span className="pd-bubble pd-bubble-review" lang={languageCode}>{zh ? "记住了!" : "Got it!"}</span>
        </>
      )}

      {variant === "practice" && (
        <>
          <span className="pd-confetti">
            {Array.from({ length: 9 }, (_, index) => <i key={index} />)}
          </span>
          <Trophy className="pd pd-trophy" size={26} />
          <Target className="pd pd-target" size={24} />
          <Medal className="pd pd-medal" size={20} />
          <Zap className="pd pd-zap" size={20} />
          <span className="pd-bubble pd-bubble-cheer" lang={languageCode}>{zh ? "加油!" : "You got this!"}</span>
        </>
      )}

      {variant === "about" && (
        <>
          <span className="pd-balloon pd-balloon-a" />
          <span className="pd-balloon pd-balloon-b" />
          <Hand className="pd pd-wave" size={26} />
          <Heart className="pd pd-heart-a" size={18} />
          <Heart className="pd pd-heart-b" size={13} />
          <Mail className="pd pd-mail" size={20} />
          <span className="pd-bubble pd-bubble-hi">Xin chào!</span>
        </>
      )}
    </div>
  );
}

/** A small penguin saying one practical tip for the page. */
export function MascotTip({ children, tone }: { children: string; tone: DoodleVariant }) {
  return (
    <p className={`mascot-tip mascot-tip-${tone}`}>
      <span className="mascot-tip-avatar" aria-hidden="true"><PenguinMark size={30} /></span>
      <span className="mascot-tip-text"><b>Mascot mách nhỏ:</b> {children}</span>
    </p>
  );
}
