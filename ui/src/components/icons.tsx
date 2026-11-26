import type { ReactNode } from "react";

type Props = { size?: number; className?: string };

function Svg({ size = 16, className, children }: Props & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const CheckIcon = (p: Props) => <Svg {...p}><path d="M5 12.5l4.5 4.5L19 7" /></Svg>;
export const XIcon = (p: Props) => <Svg {...p}><path d="M6 6l12 12M18 6L6 18" /></Svg>;
export const WarnIcon = (p: Props) => <Svg {...p}><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17.5v.01" /></Svg>;
export const ShieldIcon = (p: Props) => <Svg {...p}><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /></Svg>;
export const UndoIcon = (p: Props) => <Svg {...p}><path d="M9 7L4 12l5 5" /><path d="M4 12h10a6 6 0 010 12" transform="translate(0 -6)" /></Svg>;
export const LockIcon = (p: Props) => <Svg {...p}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></Svg>;
export const FlagIcon = (p: Props) => <Svg {...p}><path d="M6 21V4M6 5h11l-2 4 2 4H6" /></Svg>;
export const ArrowIcon = (p: Props) => <Svg {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>;
export const BanIcon = (p: Props) => <Svg {...p}><circle cx="12" cy="12" r="8" /><path d="M6.5 6.5l11 11" /></Svg>;
export const SparkIcon = (p: Props) => <Svg {...p}><path d="M12 3v5M12 16v5M3 12h5M16 12h5M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3" /></Svg>;
export const ExternalIcon = (p: Props) => <Svg {...p}><path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5" /></Svg>;
export const HelpIcon = (p: Props) => <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 015 0c0 1.5-2.5 2-2.5 3.5M12 17v.01" /></Svg>;
