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
export function extractContextualImageGenerationPrompt(message: string, conversationContext: string): string | null {
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

  return [
    `Create a polished, detailed vertical educational ${kind} from the supplied material.`,
    'Include a chronological sequence, concise explanations, discoverers or key contributors, meaningful visual illustrations, and a clear classification/organization section when relevant.',
    'Preserve the operator-provided topic, names, symbols and any supplied facts. Use curated offline references when the local poster pipeline has them; do not leave content cards empty.',
    `Source material to represent:\n${sourceContent}`,
  ].join(' ');
}



export type PosterDesignVariant = 'cards' | 'timeline' | 'orbit';

export type PosterRedesignRequest = {
  prompt: string;
  designVariant: PosterDesignVariant;
  /** The original operator brief, kept separate so repeated redesigns never nest prompts. */
  sourcePrompt: string;
};

/**
 * Detect conversational requests to redesign an existing poster. This is a
 * generation intent, not an image-analysis question: the previous factual
 * brief is reused while the visual composition is deliberately changed.
 */
export function extractContextualPosterRedesignRequest(
  message: string,
  conversationContext: string,
  previousPrompt = '',
  previousDesign: PosterDesignVariant = 'cards',
): PosterRedesignRequest | null {
  let input = normalizeRequest(message).replace(/[\]}>]+$/g, '').replace(/[.!?]+$/g, '').trim();
  input = input.replace(/^(?:no\s*no|nono|no[, ]+no)\s*/i, '').trim();
  if (!input || input.length > 1200) return null;

  const hasDesignChangeIntent = /\b(?:different|another|new|fresh|alternate|alternative|from\s+scratch|start\s+over)\b/i.test(input)
    && /\b(?:design|layout|version|one|poster|infographic|from\s+scratch|start\s+over)\b/i.test(input);
  const actionLed = /^(?:(?:please|now|try)\s+)*(?:(?:try\s+)?(?:generate|generating|create|creating|make|making|design|redesign|regenerate|redo)\b)[\s\S]*$/i.test(input);
  const scratchLed = /^(?:please\s+)?(?:start\s+from\s+scratch|start\s+over)\b[\s\S]*\b(?:create|make|generate|design)\b[\s\S]*$/i.test(input);
  const adjectiveLed = /^(?:(?:please|now)\s+)*(?:a|an)?\s*(?:different|another|new|fresh|alternate)\s+(?:one|design|version|layout|poster|infographic)\s*[.!?]*$/i.test(input);
  const asksForNewDesign = hasDesignChangeIntent && (actionLed || scratchLed || adjectiveLed);
  if (!asksForNewDesign) return null;

  const hasPosterContext = /\b(?:poster|infographic|educational\s+visual|science\s+exhibition)\b/i.test(conversationContext) || Boolean(previousPrompt.trim());
  if (!hasPosterContext) return null;

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
        // Prefer the earliest complete user brief, not the most recent
        // refinement sentence. The original subject and constraints survive.
        return (candidates.sort((a, b) => b.length - a.length)[0] || '').slice(0, 12000);
      })();

  if (!originalBrief) return null;

  const sequence: PosterDesignVariant[] = ['cards', 'timeline', 'orbit'];
  const previousIndex = Math.max(0, sequence.indexOf(previousDesign));
  const designVariant = sequence[(previousIndex + 1) % sequence.length];
  const designDirections: Record<PosterDesignVariant, string> = {
    cards: 'Use a structured editorial atlas: asymmetric feature panels, strong typographic hierarchy, a compact overview band, and grouped visual modules.',
    timeline: 'Use a genuinely new full-width chronological rail: one continuous vertical timeline, large date markers, wide event bands, and scientific vignettes aligned along the rail. Do not use a two-column tile grid.',
    orbit: 'Use a genuinely new orbital composition: a central vertical spine with alternating left/right event panels connected by nodes, a lighter scientific-journal palette, and visual motifs integrated into the panels. Do not reuse the previous card grid or timeline arrangement.',
  };

  const prompt = [
    'REDESIGN AN EXISTING EDUCATIONAL POSTER FROM SCRATCH. This is a new image-generation job, not a request for a written description.',
    `Requested redesign: ${input}`,
    `Required design variant: ${designVariant}. ${designDirections[designVariant]}`,
    'Preserve the original subject, requested items, factual requirements, useful explanations, chronology, source notes, and educational purpose. Do not copy the previous composition. Do not merely recolor it. Use a different information architecture and visual hierarchy.',
    'Create a new unique output file. Render real, readable text and meaningful vector illustrations. Never return a text-only claim that an image was created.',
    'ORIGINAL OPERATOR BRIEF TO PRESERVE:',
    originalBrief,
  ].join('\n\n').slice(0, 12000);

  return { prompt, designVariant, sourcePrompt: originalBrief };
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
