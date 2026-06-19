import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type RefObject,
} from "react";
import type { PlatformLetter } from "./mailbox";
import {
  getInitialLetterPhase,
  getLetterPhaseDelay,
  getNextAutomaticLetterPhase,
  isLetterBusy,
  type LetterOpenMode,
  type LetterPhase,
} from "./letterExperience";

type LetterReaderProps = {
  letter: PlatformLetter;
  mailboxTargetRef: RefObject<HTMLElement | null>;
  mode: LetterOpenMode;
  onRead: (letterId: string) => void;
  onStored: () => void;
};

type FlightVector = {
  x: number;
  y: number;
};

type LetterStageStyle = CSSProperties & {
  "--letter-flight-x": string;
  "--letter-flight-y": string;
};

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;

  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getElementCenter(element: Element): { x: number; y: number } {
  const rect = element.getBoundingClientRect();
  return {
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2,
  };
}

function getFlightVector(
  stageElement: HTMLElement | null,
  mailboxElement: HTMLElement | null,
): FlightVector {
  if (!stageElement || !mailboxElement) return { x: 0, y: 0 };

  const stageCenter = getElementCenter(stageElement);
  const mailboxCenter = getElementCenter(mailboxElement);

  return {
    x: Math.round(mailboxCenter.x - stageCenter.x),
    y: Math.round(mailboxCenter.y - stageCenter.y),
  };
}

export function LetterReader({
  letter,
  mailboxTargetRef,
  mode,
  onRead,
  onStored,
}: LetterReaderProps) {
  const [phase, setPhase] = useState<LetterPhase>(() => getInitialLetterPhase(mode));
  const [reduceMotion, setReduceMotion] = useState(prefersReducedMotion);
  const [flightVector, setFlightVector] = useState<FlightVector>({ x: 0, y: 0 });
  const overlayRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const readNotifiedRef = useRef(false);
  const storedNotifiedRef = useRef(false);

  const stageStyle: LetterStageStyle = useMemo(
    () => ({
      "--letter-flight-x": `${flightVector.x}px`,
      "--letter-flight-y": `${flightVector.y}px`,
    }),
    [flightVector.x, flightVector.y],
  );

  const openLetter = useCallback(() => {
    if (phase !== "sealed") return;
    setPhase("opening");
  }, [phase]);

  const closeLetter = useCallback(() => {
    if (phase !== "open") return;
    setFlightVector(getFlightVector(stageRef.current, mailboxTargetRef.current));
    setPhase("folding");
  }, [mailboxTargetRef, phase]);

  const handleOverlayClick = () => {
    if (phase === "sealed") {
      openLetter();
      return;
    }

    if (phase === "open") {
      closeLetter();
    }
  };

  const stopLetterClick = (event: ReactMouseEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  useEffect(() => {
    overlayRef.current?.focus();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotion = () => setReduceMotion(mediaQuery.matches);
    updateMotion();
    mediaQuery.addEventListener?.("change", updateMotion);

    return () => mediaQuery.removeEventListener?.("change", updateMotion);
  }, []);

  useEffect(() => {
    const nextPhase = getNextAutomaticLetterPhase(phase);
    if (!nextPhase) return;

    const timer = window.setTimeout(
      () => setPhase(nextPhase),
      getLetterPhaseDelay(phase, reduceMotion),
    );

    return () => window.clearTimeout(timer);
  }, [phase, reduceMotion]);

  useEffect(() => {
    if (phase !== "open" || readNotifiedRef.current) return;

    readNotifiedRef.current = true;
    onRead(letter.id);
  }, [letter.id, onRead, phase]);

  useEffect(() => {
    if (phase !== "stored" || storedNotifiedRef.current) return;

    storedNotifiedRef.current = true;
    onStored();
  }, [onStored, phase]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeLetter();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeLetter]);

  const busy = isLetterBusy(phase);

  return (
    <div
      className={`letter-overlay is-${phase}`}
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={letter.title}
      tabIndex={-1}
      onClick={handleOverlayClick}
    >
      <div className="letter-envelope-stage" ref={stageRef} style={stageStyle}>
        <div className="letter-envelope-shadow" aria-hidden="true" />
        <article className="letter-paper" onClick={stopLetterClick}>
          <button
            className="letter-close"
            type="button"
            aria-label="关闭信件"
            disabled={busy}
            onClick={closeLetter}
          >
            ×
          </button>
          <div className="letter-paper-inner">
            <h2>{letter.title}</h2>
            <div className="letter-body">
              {letter.paragraphs.map((paragraph, index) => (
                <p
                  className={index === 0 ? "letter-salutation" : undefined}
                  key={`${letter.id}-${index}`}
                >
                  {paragraph}
                </p>
              ))}
              <p className="letter-signature">by {letter.sender}</p>
            </div>
          </div>
        </article>
        <div className="letter-envelope-shell" onClick={stopLetterClick}>
          <div className="letter-fold-left" aria-hidden="true" />
          <div className="letter-fold-right" aria-hidden="true" />
          <div className="letter-fold-bottom" aria-hidden="true" />
        </div>
        <div className="letter-envelope-flap" aria-hidden="true" />
        <div className="letter-wax-seal" aria-hidden="true">愈</div>
      </div>
      {phase === "sealed" && <p className="letter-open-hint">点击任意位置拆信</p>}
    </div>
  );
}
