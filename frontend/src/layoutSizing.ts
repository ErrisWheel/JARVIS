export type LayoutSizes = {
  leftWidth: number;
  chatWidth: number;
  stackedChatHeight: number;
  composerHeight: number;
};

export type LayoutResizeKind = 'left-width' | 'chat-width' | 'stacked-chat-height' | 'composer-height';

export const DEFAULT_LAYOUT_SIZES: LayoutSizes = {
  leftWidth: 230,
  chatWidth: 430,
  stackedChatHeight: 680,
  composerHeight: 160,
};

const LIMITS: Record<keyof LayoutSizes, { min: number; max: number }> = {
  leftWidth: { min: 190, max: 360 },
  chatWidth: { min: 340, max: 720 },
  stackedChatHeight: { min: 420, max: 1000 },
  composerHeight: { min: 110, max: 360 },
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function normalizeLayoutSizes(value: unknown): LayoutSizes {
  const source = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const read = (key: keyof LayoutSizes): number => {
    const candidate = source[key];
    const fallback = DEFAULT_LAYOUT_SIZES[key];
    if (typeof candidate !== 'number' || !Number.isFinite(candidate)) return fallback;
    const { min, max } = LIMITS[key];
    return clamp(Math.round(candidate), min, max);
  };
  return {
    leftWidth: read('leftWidth'),
    chatWidth: read('chatWidth'),
    stackedChatHeight: read('stackedChatHeight'),
    composerHeight: read('composerHeight'),
  };
}

/** Keep the two adjustable desktop rails inside the available grid width. */
export function fitDesktopLayoutSizes(value: LayoutSizes, dashboardWidth: number): LayoutSizes {
  const sizes = normalizeLayoutSizes(value);
  if (!Number.isFinite(dashboardWidth) || dashboardWidth <= 1050) return sizes;
  const sideBudget = Math.max(530, Math.floor(dashboardWidth - 350)); // 320px center minimum + 2 × 13px grid gaps + safety.
  let leftWidth = sizes.leftWidth;
  let chatWidth = sizes.chatWidth;
  if (leftWidth + chatWidth > sideBudget) {
    leftWidth = Math.max(190, Math.min(leftWidth, sideBudget - 340));
    chatWidth = Math.max(340, Math.min(chatWidth, sideBudget - leftWidth));
    if (leftWidth + chatWidth > sideBudget) leftWidth = Math.max(190, sideBudget - chatWidth);
  }
  return { ...sizes, leftWidth, chatWidth };
}

/** Apply pointer/keyboard deltas from the original drag position. */
export function resizeLayoutSizes(
  start: LayoutSizes,
  kind: LayoutResizeKind,
  deltaX: number,
  deltaY: number,
  dashboardWidth: number,
): LayoutSizes {
  const safeWidth = Number.isFinite(dashboardWidth) && dashboardWidth > 0 ? dashboardWidth : 1440;
  if (kind === 'left-width') {
    const max = Math.max(220, Math.min(360, safeWidth - start.chatWidth - 350));
    return fitDesktopLayoutSizes({ ...start, leftWidth: clamp(Math.round(start.leftWidth + deltaX), 190, max) }, safeWidth);
  }
  if (kind === 'chat-width') {
    const max = Math.max(380, Math.min(720, safeWidth - start.leftWidth - 350));
    return fitDesktopLayoutSizes({ ...start, chatWidth: clamp(Math.round(start.chatWidth - deltaX), 340, max) }, safeWidth);
  }
  if (kind === 'stacked-chat-height') {
    return { ...start, stackedChatHeight: clamp(Math.round(start.stackedChatHeight - deltaY), LIMITS.stackedChatHeight.min, LIMITS.stackedChatHeight.max) };
  }
  return { ...start, composerHeight: clamp(Math.round(start.composerHeight - deltaY), LIMITS.composerHeight.min, LIMITS.composerHeight.max) };
}
