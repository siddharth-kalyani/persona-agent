/** Motion: only where it explains a change, 100–250 ms, transform and opacity only. Nothing animates
 * on keyboard actions, sorting, numbers, errors or blocking warnings. Reduced motion keeps fades and
 * drops travel (Fluent motion handles its own components). */
import { createPresenceComponent, motionTokens, tokens } from "@fluentui/react-components";

/** Milliseconds, for Fluent motion (the Web Animations API needs numbers). */
export const duration = {
  press: motionTokens.durationFaster, // 100
  micro: motionTokens.durationFast, // 150
  small: motionTokens.durationNormal, // 200
  medium: motionTokens.durationGentle, // 250
} as const;

export const easing = {
  enter: motionTokens.curveDecelerateMid,
  exit: motionTokens.curveAccelerateMin,
  move: motionTokens.curveEasyEaseMax,
  hover: motionTokens.curveEasyEase,
} as const;

/** The same scale as CSS variables, for makeStyles transitions. */
export const cssMotion = {
  press: tokens.durationFaster,
  micro: tokens.durationFast,
  small: tokens.durationNormal,
  enter: tokens.curveDecelerateMid,
  exit: tokens.curveAccelerateMin,
  hover: tokens.curveEasyEase,
} as const;

/** Colour-only hover feedback, for rows, nav items and clickable surfaces. */
export const hoverTransition = {
  transitionProperty: "background-color, border-color, color",
  transitionDuration: cssMotion.press,
  transitionTimingFunction: cssMotion.hover,
} as const;

/** Fade plus a small rise: content that appears because of something the user did (a draft, an
 * answer, a step finishing). Never for page loads in bulk. */
export const Rise = createPresenceComponent(({ distance = 4 }: { distance?: number }) => ({
  enter: {
    keyframes: [
      { opacity: 0, transform: `translateY(${distance}px)` },
      { opacity: 1, transform: "translateY(0)" },
    ],
    duration: duration.small,
    easing: easing.enter,
    reducedMotion: { keyframes: [{ opacity: 0 }, { opacity: 1 }], duration: duration.micro },
  },
  exit: {
    keyframes: [{ opacity: 1 }, { opacity: 0 }],
    duration: duration.micro,
    easing: easing.exit,
  },
}));
