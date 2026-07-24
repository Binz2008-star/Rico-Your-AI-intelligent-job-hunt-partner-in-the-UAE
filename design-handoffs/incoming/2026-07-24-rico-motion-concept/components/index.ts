/**
 * Rico motion kit — reusable React 18 + TypeScript components reinterpreting the
 * Lithos cursor-spotlight and Mainframe pointer-scrub techniques in Rico's
 * Atelier identity. Pointer events, RAF throttling, reduced-motion + touch
 * fallbacks, and full cleanup throughout. Truthful by construction: no fake
 * counts, employers, statuses, verification, providers, or progress.
 */
export { useReducedMotion, useFineHover, useSmoothPointer } from "./hooks";
export type { SmoothPointerOptions } from "./hooks";
export { MotionSafe, useMotionSafe } from "./MotionSafe";
export { CursorSpotlight } from "./CursorSpotlight";
export type { CursorSpotlightProps } from "./CursorSpotlight";
export { MaskedReveal } from "./MaskedReveal";
export type { MaskedRevealProps } from "./MaskedReveal";
export { LayeredAsset } from "./LayeredAsset";
export type { LayeredAssetProps } from "./LayeredAsset";
export { HeroEntrance } from "./HeroEntrance";
export type { HeroEntranceProps } from "./HeroEntrance";
export { ScrubbedMedia } from "./ScrubbedMedia";
export type { ScrubbedMediaProps } from "./ScrubbedMedia";
export { HeroTypewriter } from "./HeroTypewriter";
export type { HeroTypewriterProps } from "./HeroTypewriter";
export { HeroActionPills, RICO_STARTING_ACTIONS } from "./HeroActionPills";
export type { HeroActionPillsProps, RicoAction } from "./HeroActionPills";
export { ContextReveal } from "./ContextReveal";
export type { ContextRevealProps } from "./ContextReveal";
export { MobileNavigation } from "./MobileNavigation";
export type { MobileNavigationProps, NavLink } from "./MobileNavigation";
export { CareerTransformationHero } from "./CareerTransformationHero";
export type { CareerTransformationHeroProps } from "./CareerTransformationHero";
