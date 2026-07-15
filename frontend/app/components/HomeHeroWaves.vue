<template>
  <div class="home-hero-waves" aria-hidden="true">
    <svg viewBox="0 20 150 32" preserveAspectRatio="none" shape-rendering="auto">
      <defs>
        <path
          id="home-gentle-wave"
          d="M-160 44c30 0 58-18 88-18s58 18 88 18 58-18 88-18 58 18 88 18v48h-352z"
        />
      </defs>
      <g class="parallax">
        <use href="#home-gentle-wave" x="48" y="0" class="wave wave-1" />
        <use href="#home-gentle-wave" x="48" y="3" class="wave wave-2" />
        <use href="#home-gentle-wave" x="48" y="5" class="wave wave-3" />
        <use href="#home-gentle-wave" x="48" y="7" class="wave wave-4" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.home-hero-waves {
  pointer-events: none;
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  z-index: 2;
  height: clamp(3.5rem, 10vw, 8.75rem);
  overflow: visible;
  transform: translateZ(0);
  contain: layout style paint;
  isolation: isolate;
}

.home-hero-waves svg {
  display: block;
  width: 100%;
  height: 100%;
  transform: translateZ(0);
  backface-visibility: hidden;
}

.home-hero-waves use {
  animation: hero-wave 25s cubic-bezier(0.5, 0.5, 0.45, 0.5) infinite;
  fill: var(--ui-bg);
  will-change: transform;
}

.wave-1 {
  opacity: 0.25;
  animation-delay: -2s;
  animation-duration: 7s;
}

.wave-2 {
  opacity: 0.5;
  animation-delay: -3s;
  animation-duration: 10s;
}

.wave-3 {
  opacity: 0.75;
  animation-delay: -4s;
  animation-duration: 13s;
}

.wave-4 {
  animation-delay: -5s;
  animation-duration: 20s;
}

@keyframes hero-wave {
  from {
    transform: translate3d(-90px, 0, 0);
  }

  to {
    transform: translate3d(85px, 0, 0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-hero-waves use {
    animation: none;
  }
}
</style>
