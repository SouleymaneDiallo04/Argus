export function Logo({ size = 24, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" role="img" aria-label="Argus">
      <path d="M3 24Q24 6 45 24Q24 42 3 24Z" stroke={color} strokeWidth="2.6" />
      <polygon points="24,14 32,18.8 32,29.2 24,34 16,29.2 16,18.8" stroke={color} strokeWidth="2" />
      <circle cx="24" cy="24" r="3.4" fill={color} />
    </svg>
  );
}
