/**
 * Detect direct requests for a locally generated visual.
 * Recognises natural conversational and mildly noisy speech-to-text wording,
 * while avoiding ordinary questions about images.
 */
const visual = String.raw`(?:image|picture|photo|photograph|illustration|drawing|artwork|painting|wallpaper|concept\s+art|diagram|visual|render|scene|scenery|scenic\s+view|landscape|seascape|cityscape|portrait|still\s+life)`;
const subject = String.raw`(?:of|showing|depicting|for)\s+([\s\S]+)$`;
const visualStyle = String.raw`(?:(?:photorealistic|photo-realistic|realistic|cinematic|detailed|high-quality|beautiful|stunning|hyperrealistic|ultra-detailed|3d|anime|watercolor|oil-painting|macro|close-up)\s+){0,4}`;

const patterns: RegExp[] = [
  // "Generate/create/draw me a photo of ..."
  new RegExp(
    String.raw`^(?:(?:please)\s+)?(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?(?:generate|create|draw|paint|render|make|produce|design)\s+(?:me\s+)?(?:an?\s+)?${visualStyle}${visual}\s+${subject}`,
    'i',
  ),
  // "Show/give/get me a photo ...", including ASR substitutions like
  // "did you let me a photo of ..." for "get me a photo of ...".
  new RegExp(
    String.raw`^(?:(?:can|could|would|will|did|do)\s+you\s+)?(?:please\s+)?(?:show|give|get|fetch|make|generate|create|draw|render|let)\s+me\s+(?:see\s+)?(?:an?\s+)?${visualStyle}${visual}\s+${subject}`,
    'i',
  ),
  // "Can I see/have/get a picture of ...?"
  new RegExp(
    String.raw`^(?:can|could|may)\s+i\s+(?:see|have|get)\s+(?:an?\s+)?${visualStyle}${visual}\s+${subject}`,
    'i',
  ),
  // "Let me see a photo of ..." / "I wanna see a picture of ..."
  new RegExp(
    String.raw`^(?:please\s+)?(?:let\s+me\s+see|i\s+(?:want|wanna|need)(?:\s+to)?\s+see|i(?:'d|\s+would)\s+like\s+to\s+see)\s+(?:an?\s+)?${visualStyle}${visual}\s+${subject}`,
    'i',
  ),
  // "I want a photo of ..." / "I'd like an image of ..."
  new RegExp(
    String.raw`^(?:i\s+)?(?:want|wanna|need|would\s+like|(?:'d|would)\s+like)\s+(?:to\s+have\s+)?(?:an?\s+)?${visualStyle}${visual}\s+${subject}`,
    'i',
  ),
  // "Show me what an Iron Man suit looks like."
  /^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:show|visuali[sz]e)\s+me\s+(?:what\s+)?([\s\S]+?)\s+looks?\s+like[.!?]*$/i,
  // "Draw me a futuristic powered suit."
  /^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:draw|paint|render)\s+(?:me\s+)?([\s\S]+)$/i,
];

function cleanSubject(raw: string): string {
  return raw
    .trim()
    .replace(/[.!?,;:]+$/g, '')
    .replace(/\s+(?:please|thanks|thank\s+you)$/i, '')
    .replace(/[.!?,;:]+$/g, '')
    .trim();
}

function normalizeRequest(message: string): string {
  let input = message.trim().replace(/^(?:operator|user)\s*:\s*/i, '');
  // Allow a spoken name/address before the actual request.
  input = input.replace(/^(?:(?:hey|hello|hi)\s+)?j\.?\s*a\.?\s*r\.?\s*v\.?\s*i\.?\s*s\.?\s*[,;:\-]?\s*/i, '');
  return input.trim().replace(/\s+/g, ' ');
}

export function extractImageGenerationPrompt(message: string): string | null {
  const input = normalizeRequest(message);
  if (!input || input.length > 2400) return null;

  // Robust action-first parsing handles natural phrasing and minor ASR word-order
  // errors, e.g. "make me a picture of a robot" and "make a me picture of a robot".
  const directVisual = input.match(
    /^(?:(?:now|please|kindly)\s+)*(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?(?:generate|create|draw|paint|render|make|produce|design)\s+(?:(?:me)\s+|(?:a\s+me)\s+)?(?:an?\s+)?(?:(?:photorealistic|photo-realistic|realistic|cinematic|detailed|high-quality|beautiful|stunning|hyperrealistic|ultra-detailed|3d|anime|watercolor|oil-painting|macro|close-up)\s+){0,4}(image|picture|photo|photograph|illustration|drawing|artwork|painting|wallpaper|concept\s+art|diagram|visual|render|scene|scenery|scenic\s+view|landscape|seascape|cityscape|portrait|still\s+life)\s+(?:of|showing|depicting|for)\s+([\s\S]+)$/i,
  );
  if (directVisual?.[2]) {
    const subjectText = cleanSubject(directVisual[2]);
    if (subjectText.length >= 2 && subjectText.length <= 1800) return subjectText;
  }

  // Natural shorthand such as "give me another scenic view" omits the word image/photo.
  const sceneOnly = input.match(
    /^(?:(?:can|could|would|please)\s+you\s+)?(?:please\s+)?(?:show|give|make|generate|create|render|paint)\s+(?:me\s+)?(?:(?:another|one|a|an)\s+)?(scenic\s+view|scenery|landscape|seascape|cityscape|portrait|still\s+life|sunset|sunrise|mountain\s+view|ocean\s+view)(?:\s+(?:of|with|showing)\s+([\s\S]+))?[.!?]*$/i,
  );
  if (sceneOnly?.[1]) {
    const description = sceneOnly[2] ? ` ${sceneOnly[2]}` : '';
    return cleanSubject(`${sceneOnly[1]}${description}`).slice(0, 1800);
  }

  for (const pattern of patterns) {
    const match = input.match(pattern);
    const prompt = match?.[1] ? cleanSubject(match[1]) : '';
    // Short, valid subjects such as "a cat" should not be rejected.
    if (prompt && prompt.length >= 3 && prompt.length <= 1800) return prompt;
  }
  return null;
}



export type VisualOrientation = 'portrait' | 'landscape';

/** Normalize persisted/API orientation values at the UI boundary.
 * Legacy conversation records may contain null or unexpected values.
 */
export function normalizeVisualOrientation(value: unknown): VisualOrientation | undefined {
  return value === 'portrait' || value === 'landscape' ? value : undefined;
}

/** Detect explicit canvas orientation/aspect-ratio instructions without
 * confusing a subject such as "a landscape painting" with page orientation. */
export function extractRequestedVisualOrientation(message: string): VisualOrientation | null {
  const input = normalizeRequest(message).toLowerCase();
  if (/\b(?:16\s*:\s*9|widescreen|a3\s+landscape|landscape[ -]orientation|landscape[ -]format|make\s+(?:it|this|the\s+poster)\s+landscape|in\s+landscape|horizontal[ -]orientation|horizontal[ -]format|wide[ -]format|wide[ -]canvas)\b/.test(input)) return 'landscape';
  if (/\b(?:9\s*:\s*16|portrait[ -]orientation|portrait[ -]format|vertical[ -]orientation|vertical[ -]format|tall[ -]format)\b/.test(input)) return 'portrait';
  return null;
}

/** Stop/cancel phrases are handled by the UI control path, not sent to a model. */
export function isStopCommand(message: string): boolean {
  const input = normalizeRequest(message).replace(/[.!?]+$/g, '').trim();
  return /^(?:(?:please|jarvis)\s+)*(?:stop|cancel|abort|halt|pause|interrupt)(?:\s+(?:(?:the\s+)?(?:current\s+)?(?:image\s+generation|poster\s+generation|generation|image|poster|render|request|response|reply|task|job|process|speaking|talking|voice|listening|microphone|recording|generating|it|that|this)|now))?$/i.test(input)
    || /^(?:don't|do not)\s+(?:continue|keep going|proceed)$/i.test(input)
    || /^(?:stop|cancel|abort)\s+(?:the\s+)?(?:current\s+)?(?:image|poster|image generation|poster generation|current request|current response|current task)$/i.test(input);
}

/**
 * Detect a complete, explicit educational-poster brief. Unlike the short
 * conversational detector below, this accepts long assignment-style prompts
 * that put descriptive adjectives between the action verb and "poster".
 * The original brief is preserved verbatim (after whitespace normalization)
 * so curated subject extraction and the local poster model receive the full
 * element/topic list instead of a truncated paraphrase.
 */
export function extractExplicitPosterGenerationPrompt(message: string): string | null {
  const input = normalizeRequest(message);
  if (!input || input.length < 24 || input.length > 12000) return null;

  const hasCreationIntent = /^(?:(?:now|please|kindly)\s+)*(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?(?:create|generate|make|design|produce|render|draw|build|prepare)\b/i.test(input);
  const hasPosterFormat = /\b(?:(?:highly\s+)?(?:detailed|educational|academic|scientific|informational|professional|exhibition|classroom|research)\s+)*(?:poster|infographic|information\s+graphic)\b/i.test(input);
  if (!hasCreationIntent || !hasPosterFormat) return null;

  // The local poster API accepts up to 12,000 characters. Do not silently
  // truncate: an oversized request should be handled as an explicit error.
  return input;
}

/**
 * Resolve contextual poster/infographic requests such as "make a poster about it"
 * against the recent conversation instead of sending them to ordinary chat.
 */
export function extractContextualImageGenerationPrompt(message: string, conversationContext: string, orientation: VisualOrientation = 'portrait'): string | null {
  let input = normalizeRequest(message).replace(/[.!?]+$/g, '').trim();
  // Repair common speech-to-text / typing joins such as "theposter".
  input = input.replace(/\b(the|an?|another)(?=(?:educationalposter|poster|infographic|timeline|diagram|chart|flyer)\b)/ig, '$1 ');

  const posterRequest = /^(?:(?:now|please)\s+)*(?:can\s+you\s+|could\s+you\s+|would\s+you\s+)?(?:make|create|design|generate|produce|draw|render)\s+(?:me\s+)?(?:(?:a|an|another|the)\s+)?(educational\s+poster|poster|infographic|timeline|diagram|chart|flyer)(?:\s+(?:about|for|of)\s+(.+?))?(?:\s+now)?$/i;
  const followThrough = /^(?:(?:now|please)\s+)*(?:generate|create|make|render|produce)\s+(?:(?:it|that|this|the\s+poster|the\s+image)\s+)?(?:using|with)\s+sdxl$/i;

  // A refinement such as "make it detailed with descriptions and visuals" is
  // an image request only when the recent conversation already contains a
  // poster/timeline request. This prevents ordinary prose edits being routed
  // to image generation by accident.
  const posterContextPresent = /\b(?:poster|infographic|timeline)\b/i.test(conversationContext);
  const posterRefinement = posterContextPresent &&
    /^(?:(?:now|please)\s+)*(?:make|update|improve|revise|redo|regenerate|expand|enhance)\s+(?:it|that|this|the\s+poster|the\s+infographic|the\s+timeline)\b[\s\S]*\b(?:detail|detailed|description|visual|illustration|explanation|information|content|label|date|text)s?\b[\s\S]*$/i.test(input);

  const match = input.match(posterRequest);
  if (!match && !followThrough.test(input) && !posterRefinement) return null;

  const kind = match?.[1]?.toLowerCase() || 'poster';
  const subject = match?.[2]?.trim() || '';
  const referentialSubject = posterRefinement || /^(?:it|that|this|them|these(?:\s+(?:elements|items|topics))?|those(?:\s+(?:elements|items|topics))?|the above|the topic|the elements(?:\s+(?:we|i)\s+(?:listed|mentioned|provided))?)$/i.test(subject);

  // Keep the original operator-provided subject/list even if many assistant
  // replies followed it. Prioritize operator turns and preserve the initial
  // poster brief; assistant claims are deliberately not used as source facts.
  const lines = conversationContext.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const operatorLines = lines.filter(line => /^Operator:/i.test(line));
  const anchorIndex = operatorLines.findIndex(line =>
    /\b(?:poster|infographic|timeline)\b/i.test(line) &&
    /\b(?:element|topic|discovery|history|classification|organization|organisation)s?\b/i.test(line),
  );
  const anchor = anchorIndex >= 0 ? operatorLines[anchorIndex] : '';
  const related = operatorLines.filter(line =>
    /\b(?:element|symbol|discovery|chronolog|classification|organization|organisation|year|date|periodic table)\b/i.test(line),
  );
  const selectedLines = [...new Set([anchor, ...related.slice(-6)].filter(Boolean))];
  let context = selectedLines.join('\n');
  if (context.length > 1500) {
    // Preserve the anchor first, then use the newest related user notes.
    const tail = selectedLines.filter(line => line !== anchor).join('\n').slice(-Math.max(0, 1500 - anchor.length - 1));
    context = [anchor.slice(0, 1200), tail].filter(Boolean).join('\n');
  }

  const explicitSubject = subject && !referentialSubject ? subject.slice(0, 300) : '';
  const sourceContent = explicitSubject
    ? `Explicit poster subject from the operator: ${explicitSubject}${context ? `\nRelevant operator-provided context:\n${context}` : ''}`
    : context;
  if (!sourceContent) return null;

  const orientationLabel = orientation === 'landscape' ? 'wide 16:9 horizontal' : 'vertical portrait';
  return [
    `Create a polished, detailed ${orientationLabel} educational ${kind} from the supplied material.`,
    'Include a chronological sequence, concise explanations, discoverers or key contributors, meaningful visual illustrations, and a clear classification/organization section when relevant.',
    'Preserve the operator-provided topic, names, symbols and any supplied facts. Use curated offline references when the local poster pipeline has them; do not leave content cards empty.',
    `Source material to represent:\n${sourceContent}`,
  ].join(' ');
}



export type PosterDesignVariant = 'cards' | 'timeline' | 'orbit' | 'blueprint' | 'museum' | 'fieldnotes' | 'collage';
export type PosterEditOperation = 'new' | 'refine' | 'redesign';
export type PosterVisualStyle = 'default' | 'artsy' | 'technical' | 'vintage' | 'museum' | 'collage' | 'watercolor' | 'minimal';

export type PosterRedesignRequest = {
  prompt: string;
  operation: 'refine' | 'redesign';
  designVariant: PosterDesignVariant;
  visualStyle: PosterVisualStyle;
  visualDensity: 'normal' | 'rich' | 'high';
  designNotes: string;
  /** Original operator brief, kept separate so edits never nest prior edit prompts. */
  sourcePrompt: string;
  orientation: VisualOrientation;
};

const POSTER_LAYOUTS: PosterDesignVariant[] = [
  'cards', 'timeline', 'orbit', 'blueprint', 'museum', 'fieldnotes', 'collage',
];

function inferPosterVisualStyle(input: string): PosterVisualStyle {
  if (/\b(?:artsy|artistic|creative|illustrated|hand[ -]?drawn|playful|expressive)\b/i.test(input)) return 'artsy';
  if (/\b(?:blueprint|technical|schematic|engineering|technical drawing)\b/i.test(input)) return 'technical';
  if (/\b(?:vintage|retro|antique|archival|aged paper|old textbook)\b/i.test(input)) return 'vintage';
  if (/\b(?:museum|gallery|exhibition)\b/i.test(input)) return 'museum';
  if (/\b(?:collage|mixed media|cut[ -]?paper|scrapbook)\b/i.test(input)) return 'collage';
  if (/\b(?:watercolou?r|painted|gouache|ink wash)\b/i.test(input)) return 'watercolor';
  if (/\b(?:minimal|minimalist|clean and simple|restrained)\b/i.test(input)) return 'minimal';
  return 'default';
}

function chooseNextPosterLayout(
  previous: PosterDesignVariant,
  recent: PosterDesignVariant[],
  requested: PosterDesignVariant | null,
  variationKey: string,
): PosterDesignVariant {
  if (requested) return requested;
  // Avoid the last four families, then choose among the remaining options from
  // a prompt/history fingerprint. This is intentionally not a fixed rotation.
  const recentSet = new Set(recent.slice(-4));
  let candidates = POSTER_LAYOUTS.filter(layout => layout !== previous && !recentSet.has(layout));
  if (!candidates.length) candidates = POSTER_LAYOUTS.filter(layout => layout !== previous);
  if (!candidates.length) return previous;
  let fingerprint = 2166136261;
  const value = `${variationKey}|${previous}|${recent.join(',')}`;
  for (let index = 0; index < value.length; index += 1) {
    fingerprint ^= value.charCodeAt(index);
    fingerprint = Math.imul(fingerprint, 16777619);
  }
  return candidates[(fingerprint >>> 0) % candidates.length];
}

/**
 * Route follow-up poster instructions as either a refinement of the latest
 * composition or a new composition from scratch. The original source brief is
 * preserved independently from the visual direction supplied by the operator.
 */
export function extractContextualPosterRedesignRequest(
  message: string,
  conversationContext: string,
  previousPrompt = '',
  previousDesign: PosterDesignVariant = 'cards',
  recentDesigns: PosterDesignVariant[] = [],
  previousOrientation: VisualOrientation = 'portrait',
): PosterRedesignRequest | null {
  let input = normalizeRequest(message).replace(/[\]}>]+$/g, '').replace(/[.!?]+$/g, '').trim();
  input = input.replace(/^(?:no\s*no|nono|no[, ]+no)\s*/i, '').trim();
  if (!input || input.length > 1600) return null;

  const hasPosterContext = /\b(?:poster|infographic|educational\s+visual|science\s+exhibition)\b/i.test(conversationContext)
    || Boolean(previousPrompt.trim());
  if (!hasPosterContext) return null;

  const explicitScratch = /\b(?:from\s+scratch|start\s+over|start\s+from\s+scratch|start\s+again|new\s+composition|completely\s+new|totally\s+different|reset\s+(?:the\s+)?poster|restart\s+(?:the\s+)?(?:poster|design|layout|composition))\b/i.test(input);
  const differentDesignPhrase = /\b(?:very\s+different|different\s+design|different\s+layout|another\s+design|new\s+design|new\s+one|another\s+one|new\s+poster|redesign)\b/i.test(input);
  const actionLead = /^(?:(?:please|now|nono|no\s*no|then|okay|ok|try|can\s+you|could\s+you)\s+)*(?:try|generate|generating|create|creating|make|making|design|redesign|regenerate|redo|start|give|do|put|add|include|improve|enhance|refine|polish|new)\b/i.test(input);
  const improvementCue = /\b(?:more\s+visuals?|visuals?|artsy|artistic|illustrations?|design\s+elements?|empty\s+spaces?|negative\s+space|decorate|decorative|fill|add|put|include|improve|enhance|refine|polish|cleaner|less\s+clutter|different\s+colors?|color\s+scheme|typography|spacing|composition|layout|style|visual\s+interest|educational\s+design|more\s+educational|instructional|teaching\s+design|learning\s+visuals?)\b/i.test(input);
  const styleOnlyCue = /^(?:(?:please|now|try|do)\s+)*(?:something|one|it|that|this)?\s*(?:more\s+)?(?:artsy|artistic|creative|vintage|retro|technical|blueprint|museum|collage|watercolor|minimalist|minimal|educational|instructional)\b/i.test(input);
  const softFollowup = actionLead && improvementCue;
  const simpleRetry = /^(?:(?:then|now|please|okay|ok)\s+)*(?:(?:give\s+me\s+)?(?:a\s+)?new\s+one|(?:give\s+me\s+)?one|make\s+another|generate\s+another|do\s+it\s+again|make\s+me\s+a\s+new\s+poster)(?:[ ,;:-]+(?:same\s+content[, ]*)?(?:in\s+)?(?:landscape|portrait)(?:\s+(?:format|orientation))?)?$/i.test(input)
    || /^give\s+me\s+one(?:\s+then)?$/i.test(input);
  const educationalDesignFollowup = /^(?:(?:please|now|try)\s+)*(?:something|make\s+it|give\s+it|i\s+want\s+it)\s+(?:with\s+)?(?:a\s+)?(?:more\s+)?(?:educational|instructional|teaching|learning)(?:\s+(?:design|visuals?|layout|elements?))?$/i.test(input);
  const isRedesign = explicitScratch || simpleRetry || (differentDesignPhrase && actionLead);
  const isRefinement = !isRedesign && (softFollowup || styleOnlyCue || educationalDesignFollowup || /^(?:try\s+)?something\s+(?:with\s+)?(?:more\s+)?(?:visuals?|artsy|artistic|creative|educational)\b/i.test(input));
  if (!isRedesign && !isRefinement) return null;

  const lines = conversationContext.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const operatorLines = lines
    .filter(line => /^Operator:/i.test(line))
    .map(line => line.replace(/^Operator:\s*/i, '').trim());
  const stripSyntheticPrefix = (value: string) => value.replace(/^Generate an image:\s*/i, '').trim();
  const previousValue = stripSyntheticPrefix(previousPrompt);
  const sourceMarker = 'ORIGINAL OPERATOR BRIEF TO PRESERVE:';
  const sourceMarkerIndex = previousValue.lastIndexOf(sourceMarker);
  const recoveredPreviousBrief = sourceMarkerIndex >= 0
    ? previousValue.slice(sourceMarkerIndex + sourceMarker.length).trim()
    : previousValue;
  const originalBrief = recoveredPreviousBrief.trim()
    ? recoveredPreviousBrief.trim().slice(0, 12000)
    : (() => {
        const candidates = operatorLines.map(stripSyntheticPrefix).filter(line =>
          line.length >= 40 && /\b(?:poster|infographic)\b/i.test(line) &&
          /\b(?:create|generate|make|design|produce|render|draw|prepare)\b/i.test(line),
        );
        return (candidates.sort((a, b) => b.length - a.length)[0] || '').slice(0, 12000);
      })();
  if (!originalBrief) return null;

  const requestedLayoutMatch = input.match(/\b(cards?|timeline|orbit(?:al)?|radial|blueprint|museum|gallery|field[ -]?notes?|collage|editorial)\b/i);
  let requestedLayout: PosterDesignVariant | null = null;
  if (requestedLayoutMatch) {
    const key = requestedLayoutMatch[1].toLowerCase().replace(/s$/, '');
    if (key === 'radial' || key === 'orbital') requestedLayout = 'orbit';
    else if (key === 'field-notes' || key === 'fieldnotes') requestedLayout = 'fieldnotes';
    else if (key === 'gallery') requestedLayout = 'museum';
    else if (key === 'editorial') requestedLayout = 'cards';
    else if (POSTER_LAYOUTS.includes(key as PosterDesignVariant)) requestedLayout = key as PosterDesignVariant;
  }

  const visualStyle = inferPosterVisualStyle(input);
  const visualDensity = /\b(?:more\s+visuals?|fill\s+(?:the\s+)?empty|empty\s+spaces?|decorat|artsy|artistic|illustrat|visual\s+interest)\b/i.test(input)
    ? 'high'
    : /\b(?:more\s+detail|richer|visual\s+elements?)\b/i.test(input) ? 'rich' : 'normal';
  const orientation = extractRequestedVisualOrientation(input) || previousOrientation;
  const operation: 'refine' | 'redesign' = isRedesign ? 'redesign' : 'refine';
  const designVariant = operation === 'refine'
    ? (requestedLayout || previousDesign)
    : chooseNextPosterLayout(previousDesign, recentDesigns.length ? recentDesigns : [previousDesign], requestedLayout, input);

  const prompt = [
    operation === 'refine'
      ? 'REFINE THE EXISTING EDUCATIONAL POSTER. Preserve its facts, wording, ordering and educational purpose; implement the operator visual changes below.'
      : 'CREATE A NEW POSTER COMPOSITION FROM SCRATCH. Preserve the existing poster content and factual material, but replace the composition rather than reusing the last design.',
    `Operator visual direction: ${input}`,
    `Operation: ${operation}. Layout family: ${designVariant}. Visual style: ${visualStyle}. Visual density: ${visualDensity}. Output orientation: ${orientation}.`,
    orientation === 'landscape' ? 'HARD CANVAS CONSTRAINT: render a 16:9 horizontal landscape poster, 1920 × 1080. Do not produce portrait output.' : 'HARD CANVAS CONSTRAINT: render a vertical portrait poster, 1536 × 2048.',
    'Do not copy the previous composition. Do not cycle through a fixed three-template sequence. Do not describe an image as generated unless a new verified PNG and SVG have been saved.',
    `ORIGINAL OPERATOR BRIEF TO PRESERVE:\n${originalBrief}`,
  ].join('\n\n').slice(0, 12000);

  return { prompt, operation, designVariant, visualStyle, visualDensity, designNotes: input, sourcePrompt: originalBrief, orientation };
}

/** Route questions about the most recently generated visual to local vision analysis. */
export function isGeneratedImageFollowUp(message: string): boolean {
  const value = message.toLowerCase().replace(/\s+/g, ' ').trim();
  if (!value) return false;
  const imageNoun = String.raw`(?:image|images|picture|pictures|photo|photos|poster|preview|result)`;
  const refersToImage = new RegExp(
    String.raw`\b(?:(?:this|that|the|these|those|my|your|generated)\s+${imageNoun}|${imageNoun}\s+(?:you|we)\s+(?:created|generated|made))\b`,
  ).test(value);
  const asksAboutImage = /\b(?:what|why|how|where|describe|analy[sz]e|inspect|look|see|compare|identify|recognize|explain|import|display|show|include|match|contain|depict|read)\b/.test(value);
  const directImageQuestion = /\b(?:what(?:'s| is) (?:in|shown|depicted)|can you see (?:it|this|that)|why can'?t you (?:see|import|view) (?:it|this|that|the )?(?:images?|pictures?|photos?)?|(?:show|display|open|load) (?:the )?(?:images?|pictures?|photos?))\b/.test(value);
  const currentVisualReference = /^(?:what(?:'s| is) this|what am i looking at|describe it|tell me what you see|does it match(?: the prompt)?)[.!?]*$/.test(value);
  return (refersToImage && asksAboutImage) || directImageQuestion || currentVisualReference;
}

/** Detects a text-model claim that an image was created when no image-service
 * completion event or verified local file was returned. */
export function isUnverifiedImageCreationClaim(response: string): boolean {
  const value = normalizeRequest(response).toLowerCase();
  const completedAction = /\b(?:created|generated|rendered|redesigned|produced|saved|finished|completed)\b/.test(value);
  const visualTarget = /\b(?:image|picture|poster|infographic|visual|layout|design|png|svg)\b/.test(value);
  const completionContext = /\b(?:locally|new\s+layout|new\s+design|from\s+scratch|ready|saved|generated|rendered)\b/.test(value);
  return completedAction && visualTarget && completionContext;
}
