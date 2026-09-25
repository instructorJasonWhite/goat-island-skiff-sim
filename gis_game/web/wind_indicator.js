/* Apparent wind-from bearing in a boat-fixed dial: bow is up, starboard right. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.GISWindIndicator = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function nextNeedleRotation(signedFromBow, previous) {
    const target = signedFromBow - 90; // The glyph points right at 0 CSS degrees.
    if (!Number.isFinite(previous)) return target;
    const shortestTurn = ((target - previous + 540) % 360 + 360) % 360 - 180;
    return previous + shortestTurn;
  }

  function bearingLabel(signedFromBow) {
    const angle = Math.round(Math.abs(signedFromBow));
    if (angle <= 1) return { short: '0° AHEAD', detail: 'from dead ahead' };
    if (angle >= 179) return { short: '180° ASTERN', detail: 'from astern' };
    const starboard = signedFromBow > 0;
    return {
      short: `${angle}° ${starboard ? 'STBD' : 'PORT'}`,
      detail: `from ${angle}° ${starboard ? 'starboard' : 'port'} of bow`,
    };
  }

  return { nextNeedleRotation, bearingLabel };
});
