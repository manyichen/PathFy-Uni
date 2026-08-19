export const journeyConfig = {
  idle: {
    lineAlpha: 0.82,
    periodMs: 4200,
    arcHeight: 76
  },
  sprint: {
    returnMs: 680,
    sprintEndMs: 1540,
    impactEndMs: 1680
  },
  fracture: {
    startMs: 1620,
    endMs: 1980,
    lineParticles: 148,
    sparksDesktop: 260,
    sparksMobile: 90
  },
  routes: {
    startMs: 1740,
    extendEndMs: 4300,
    fadeStartMs: 3400,
    fadeEndMs: 5000,
    desktopCount: 9,
    mobileCount: 7
  },
  reveal: {
    navigateAt: 1580,
    peelStart: 1740,
    peelEnd: 5000,
    finishAt: 5200
  },
  colors: ['#ff5a70', '#ff8a3d', '#ffd84d', '#75f07a', '#36e5ca', '#50bfff', '#a680ff', '#ff6fcf']
} as const
