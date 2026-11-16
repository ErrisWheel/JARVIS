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
 * Resolve contextual poster/infographic requests such as "make a poster about it"
 * against the recent conversation instead of sending them to ordinary chat.
 */
export function extractContextualImageGenerationPrompt(message: string, conversationContext: string): string | null {
  let input = normalizeRequest(message)
    .replace(/\b(the|an?|another)(?=(?:educationalposter|poster|infographic|timeline|diagram|chart|flyer)\b)/ig, '$1 ')
    .replace(/[.!?]+$/g, '')
    .trim();
  input = input.replace(/\s+/g, ' ');

  // Accept both a direct subject and short follow-throughs such as
  // "create the poster now", "make theposter", and "render it with SDXL".
  const posterRequest = /^(?:(?:now|please)\s+)*(?:can\s+you\s+|could\s+you\s+|would\s+you\s+)?(?:please\s+)?(?:make|create|design|generate|produce|draw|render)\s+(?:me\s+)?(?:(?:a|an|another|the)\s+)?(educational\s+poster|poster|infographic|timeline|diagram|chart|flyer)(?:\s+(?:about|for|of|covering|on)\s+(.+?))?(?:\s+(?:right\s+)?now)?(?:\s+please)?$/i;
  const followThrough = /^(?:(?:now|please)\s+)*(?:generate|create|make|render|produce)\s+(?:(?:it|that|this|the\s+poster|the\s+image)\s+)?(?:using|with)\s+(?:local\s+)?sdxl(?:\s+now)?$/i;
  const imageOnlyFollowThrough = /^(?:(?:now|please)\s+)*(?:generate|create|make|render)\s+(?:it|that|this|the\s+poster|the\s+image)(?:\s+now)?$/i;
  const match = input.match(posterRequest);
  if (!match && !followThrough.test(input) && !imageOnlyFollowThrough.test(input)) return null;

  const kind = match?.[1]?.toLowerCase() || 'poster';
  const subject = match?.[2]?.trim() || '';
  const referentialSubject = /^(?:it|that|this|them|these(?:\s+(?:elements|items|topics))?|those(?:\s+(?:elements|items|topics))?|the above|the topic|the elements(?:\s+(?:we|i)\s+(?:listed|mentioned|provided))?)$/i.test(subject);
  const rawContext = conversationContext.trim();
  // The backend caps image prompts at 2,400 characters. Reserve room for the
  // visual instructions and retain the newest portion of the actual discussion.
  const context = rawContext.slice(-(subject && !referentialSubject ? 1050 : 1500));
  const sourceContent = subject && !referentialSubject
    ? `Explicit poster subject from the operator: ${subject}${context ? `\nRecent conversation context:\n${context}` : ''}`
    : context;
  if (!sourceContent) return null;

  return [
    `Create a polished vertical educational ${kind} using the supplied conversation material.`,
    'This is an image-generation request: render the actual finished poster as an image, not a text outline or a description of a poster.',
    'Use a clear visual hierarchy, balanced spacing, a refined scientific/editorial design, and a chronological layout when dates or events are present.',
    'Preserve every supplied name, symbol, date, and ordering exactly. Include only the subjects requested or discussed; do not add unrelated items or invent facts. Keep wording concise and legible, with clear labels, readable typography, and strong contrast.',
    `Source material to represent:\n${sourceContent}`,
  ].join(' ').slice(0, 2300);
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
