/**
 * Decorative Poké Ball watermark for the hero.
 *
 * Drawn as geometry rather than an image or emoji so it inherits the accent
 * colour and stays crisp at any size. It sits at low opacity behind the
 * heading: a hint of the object the app is about, not a sticker.
 *
 * Purely decorative, so it is hidden from assistive technology.
 */
export function PokeballMark({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 100 100"
      aria-hidden="true"
      focusable="false"
      role="presentation"
    >
      {/* Top half, filled just enough to read as a ball rather than a ring. */}
      <path d="M4 50a46 46 0 0 1 92 0Z" fill="currentColor" opacity="0.28" />
      {/* Outer shell. */}
      <circle cx="50" cy="50" r="46" fill="none" stroke="currentColor" strokeWidth="6" />
      {/* The band stops at the shell, which is what makes it a ball. */}
      <path d="M6 50h88" stroke="currentColor" strokeWidth="6" strokeLinecap="butt" />
      {/* Centre button: a ring around a solid core. */}
      <circle cx="50" cy="50" r="15" fill="var(--surface)" />
      <circle cx="50" cy="50" r="15" fill="none" stroke="currentColor" strokeWidth="6" />
      <circle cx="50" cy="50" r="6" fill="currentColor" />
    </svg>
  );
}
