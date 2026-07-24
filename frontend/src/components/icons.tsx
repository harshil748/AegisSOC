import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base(props: IconProps, children: React.ReactNode) {
  const { size = 16, ...rest } = props;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function ShieldIcon(props: IconProps) {
  return base(props, <path d="M12 3 4 6.5v6c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10v-6L12 3Z" />);
}
export function AlertQueueIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M10.3 3.9 2.6 17.5a1.6 1.6 0 0 0 1.4 2.4h16a1.6 1.6 0 0 0 1.4-2.4L13.7 3.9a1.6 1.6 0 0 0-2.8 0Z" />
      <path d="M12 9v4" />
      <path d="M12 16.2h.01" />
    </>,
  );
}
export function GraphIcon(props: IconProps) {
  return base(
    props,
    <>
      <circle cx="6" cy="6" r="2.3" />
      <circle cx="18" cy="6" r="2.3" />
      <circle cx="12" cy="18" r="2.3" />
      <path d="M7.8 7.3 10.3 16" />
      <path d="M16.2 7.3 13.7 16" />
      <path d="M8.3 6h7.4" />
    </>,
  );
}
export function CaseIcon(props: IconProps) {
  return base(
    props,
    <>
      <rect x="3" y="7" width="18" height="12" rx="2" />
      <path d="M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7" />
    </>,
  );
}
export function ResponseIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="m20 6-11 11-5-5" />
    </>,
  );
}
export function AuditIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M9 3h6l1 3H8l1-3Z" />
      <rect x="4" y="6" width="16" height="15" rx="2" />
      <path d="M8 12h8M8 16h8" />
    </>,
  );
}
export function MetricsIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M4 20V10M11 20V4M18 20v-7" />
    </>,
  );
}
export function DemoIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
      <path d="m10 9 5 3-5 3V9Z" />
    </>,
  );
}
export function ChevronDownIcon(props: IconProps) {
  return base(props, <path d="m6 9 6 6 6-6" />);
}
export function XIcon(props: IconProps) {
  return base(props, <path d="M18 6 6 18M6 6l12 12" />);
}
export function CheckIcon(props: IconProps) {
  return base(props, <path d="m5 13 4 4L19 7" />);
}
export function SearchIcon(props: IconProps) {
  return base(
    props,
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>,
  );
}
export function RefreshIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M21 12a9 9 0 1 1-2.6-6.4" />
      <path d="M21 4v5h-5" />
    </>,
  );
}
export function ExternalLinkIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M14 4h6v6" />
      <path d="M20 4 10 14" />
      <path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" />
    </>,
  );
}
export function InfoIcon(props: IconProps) {
  return base(
    props,
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" />
      <path d="M12 8h.01" />
    </>,
  );
}
export function AlertTriangleIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M10.3 3.9 2.6 17.5a1.6 1.6 0 0 0 1.4 2.4h16a1.6 1.6 0 0 0 1.4-2.4L13.7 3.9a1.6 1.6 0 0 0-2.8 0Z" />
      <path d="M12 9v4" />
      <path d="M12 16.2h.01" />
    </>,
  );
}
export function LogOutIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5" />
      <path d="M21 12H9" />
    </>,
  );
}
export function InboxEmptyIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M4 12h4l2 3h4l2-3h4" />
      <path d="M5.5 5h13l2.5 7v6a2 2 0 0 1-2 2h-14a2 2 0 0 1-2-2v-6l2.5-7Z" />
    </>,
  );
}
export function PlayIcon(props: IconProps) {
  return base(props, <path d="M7 4v16l13-8L7 4Z" />);
}
export function ClockIcon(props: IconProps) {
  return base(
    props,
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </>,
  );
}
export function DownloadIcon(props: IconProps) {
  return base(
    props,
    <>
      <path d="M12 3v12" />
      <path d="m7 11 5 5 5-5" />
      <path d="M5 21h14" />
    </>,
  );
}
