import Image from "next/image";

type IconProps = { size?: number; strokeWidth?: number };

function Stroke({ size = 16, strokeWidth = 2, d }: IconProps & { d: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export const CheckIcon = (p: IconProps) => <Stroke {...p} d="M5 12.5l4.5 4.5L19 7.5" />;
export const XIcon = (p: IconProps) => <Stroke {...p} d="M6 6l12 12M18 6L6 18" />;
export const ArrowRightIcon = (p: IconProps) => <Stroke {...p} d="M5 12h14M13 6l6 6-6 6" />;
export const ExchangeIcon = (p: IconProps) => <Stroke {...p} d="M4 7h12l-3-3M20 17H8l3 3" />;
export const MessageIcon = (p: IconProps) => <Stroke {...p} d="M4 5h16v11H9l-5 4z" />;
export const RefreshIcon = (p: IconProps) => <Stroke {...p} d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" />;
export const ChevronDownIcon = (p: IconProps) => <Stroke {...p} d="M6 9l6 6 6-6" />;
export const PlusIcon = (p: IconProps) => <Stroke {...p} d="M12 5v14M5 12h14" />;
export const ExportIcon = (p: IconProps) => <Stroke {...p} d="M12 3v12M7 8l5-5 5 5M5 14v5h14v-5" />;
export const SparkIcon = (p: IconProps) => (
  <Stroke {...p} d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6" />
);

export function PanelIcon({ size = 15 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="9" cy="8" r="3" />
      <circle cx="17" cy="9" r="2.5" />
      <path d="M3 19c0-3.3 2.7-5 6-5s6 1.7 6 5M15 14.5c3 0 6 1.4 6 4.5" />
    </svg>
  );
}

export function PlayIcon({ size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
    </svg>
  );
}

export function StopIcon({ size = 12 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden="true">
      <rect width="12" height="12" rx="2.5" fill="currentColor" />
    </svg>
  );
}

/** The Hawk mark: a hawk in flight, wings spread, under a small sun. */
export function HawkMark({ size = 28, sun = "var(--accent)", ink = "currentColor" }: { size?: number; sun?: string; ink?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true">
      <circle cx="21.5" cy="5.5" r="2.6" fill={sun} />
      <path
        d="M1.5 12.2C5.4 10.6 9.3 11 12.4 13.6L14 15l1.6-1.4c3.1-2.6 7-3 10.9-1.4-3.4.5-6.4 2.3-8.3 5.1L15.6 21 14 25.5 12.4 21l-2.6-3.7C7.9 14.5 4.9 12.7 1.5 12.2Z"
        fill={ink}
      />
      <path d="M12.6 13.9 14 12l1.4 1.9L14 15.2Z" fill={ink} />
    </svg>
  );
}

/** A provider/model logo from /public/logos. Decorative unless `alt` is given. */
export function ModelLogo({ src, size, alt = "", className }: { src: string; size: number; alt?: string; className?: string }) {
  return <Image src={src} alt={alt} width={size} height={size} unoptimized className={className} />;
}
