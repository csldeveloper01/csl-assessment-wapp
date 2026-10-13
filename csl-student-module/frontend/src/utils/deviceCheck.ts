/**
 * Device and Viewport Eligibility Utility for CSL Initial Assessment
 * 
 * Requirement: The assessment is designed and restricted for laptop/desktop use.
 * Detects small-screen/mobile contexts and unsuitable viewport dimensions.
 */

export const MIN_SUPPORTED_WIDTH = 1024;
export const MIN_SUPPORTED_HEIGHT = 600;

export interface DeviceEligibilityResult {
  eligible: boolean;
  reason?: 'mobile' | 'viewport_small';
  currentWidth: number;
  currentHeight: number;
  minWidth: number;
  minHeight: number;
}

export function checkDeviceEligibility(
  minWidth: number = MIN_SUPPORTED_WIDTH,
  minHeight: number = MIN_SUPPORTED_HEIGHT
): DeviceEligibilityResult {
  const currentWidth = window.innerWidth;
  const currentHeight = window.innerHeight;
  const ua = (navigator.userAgent || '').toLowerCase();

  // Explicit Mobile OS / device patterns
  const isMobileOS = /android|iphone|ipod|blackberry|windows phone|iemobile|opera mini/i.test(ua);
  
  // Touch-primary small physical screen (mobile phones & small tablets)
  const isSmallScreenTouch =
    ('ontouchstart' in window || navigator.maxTouchPoints > 1) &&
    (window.screen.width < 1024 || window.screen.height < 600);

  if (isMobileOS || isSmallScreenTouch) {
    return {
      eligible: false,
      reason: 'mobile',
      currentWidth,
      currentHeight,
      minWidth,
      minHeight,
    };
  }

  // Viewport dimensions (e.g. unmaximized browser window on a laptop)
  if (currentWidth < minWidth || currentHeight < minHeight) {
    return {
      eligible: false,
      reason: 'viewport_small',
      currentWidth,
      currentHeight,
      minWidth,
      minHeight,
    };
  }

  return {
    eligible: true,
    currentWidth,
    currentHeight,
    minWidth,
    minHeight,
  };
}
