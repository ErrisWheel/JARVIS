import test from 'node:test';
import assert from 'node:assert/strict';
import { extractExplicitPosterGenerationPrompt, extractContextualPosterRedesignRequest, extractImageGenerationPrompt, extractRequestedVisualOrientation, normalizeVisualOrientation, isStopCommand, isUnverifiedImageCreationClaim } from '../src/imageIntent.ts';

const fullBrief = `Create a highly detailed, visually engaging, and scientifically accurate educational poster illustrating the chronological timeline of the discovery and the organizations or institutions involved in the discovery of the following chemical elements: Md (Mendelevium), F (Fluorine), Cl (Chlorine), Br (Bromine), I (Iodine), At (Astatine), Ts (Tennessine), Yb (Ytterbium), No (Nobelium), and He (Helium). Required Content. Organize the elements according to their actual discovery dates, from earliest to most recent. For each element, include the Element Name and Symbol, Discovery Date or Year, Discoverer(s), Discovery Location, Organization or Institution, Discovery Background, and Historical Significance. Poster Design and Visual Presentation: use a chronological timeline layout, distinct information sections, scientifically relevant illustrations, laboratory imagery, historical photographs where appropriate, periodic-table-style element boxes, informative icons, a clear visual hierarchy, readable typography and balanced spacing. Additional Requirements: ensure historical accuracy, distinguish initial discovery, first isolation, synthesis and official recognition, identify collaborating institutions and countries, avoid overcrowding, include an introduction, conclusion and credible references. The final output should resemble a professional university-level educational infographic suitable for an academic presentation. Include a legend, an explanation of the chronology, scientific context, comparisons between element families, atomic-number information, discovery-method descriptions, the institutional setting for each research team, a readable bibliography, and carefully placed captions. Give the timeline a clear beginning and end, use connecting lines and year markers, provide enough white space for the reader to follow the history, and use visual examples that help explain the actual discovery process rather than decorative filler. The complete poster should be useful to a student studying chemistry and to a visitor viewing a science exhibition. Do not reduce the poster to a list of element names or empty cards. svg`;

const longBrief = `${fullBrief} Add detailed visual explanations for every scientific method, clarify the institutional history, include a meaningful periodic-table diagram, annotate laboratory equipment, provide a compact source list, compare the element families, and use educational illustrations that explain discovery rather than decorative filler. Ensure the complete composition is suitable for a university science exhibition and remains legible when printed.`;

test('recognizes the operator full-length element poster brief', () => {
  assert.ok(longBrief.length > 2400);
  assert.equal(extractExplicitPosterGenerationPrompt(longBrief), longBrief);
});

test('recognizes brief-style poster prompts with adjectives between action and noun', () => {
  const prompt = 'Create a highly detailed and scientifically accurate educational poster about cellular respiration. Include annotated diagrams, processes, examples and references.';
  assert.equal(extractExplicitPosterGenerationPrompt(prompt), prompt);
});

test('does not turn image questions into poster generation', () => {
  assert.equal(extractExplicitPosterGenerationPrompt('Can you explain what makes a good educational poster?'), null);
});

test('does not misroute ordinary SDXL image requests', () => {
  assert.equal(extractExplicitPosterGenerationPrompt('Create a cinematic image of a futuristic laboratory.'), null);
});


const operatorBrief = "Create a highly detailed, visually engaging, and scientifically accurate educational poster illustrating the chronological timeline of the discovery and the organizations or institutions involved in the discovery of the following chemical elements: Md (Mendelevium), F (Fluorine), Cl (Chlorine), Br (Bromine), I (Iodine), At (Astatine), Ts (Tennessine), Yb (Ytterbium), No (Nobelium), and He (Helium).\n\nRequired Content\n\nOrganize the elements according to their actual discovery dates, from earliest to most recent. For each element, include:\n\nElement Name and Symbol – Clearly display its complete name and chemical symbol.\nDiscovery Date or Year – Indicate when the element was first discovered or identified.\nDiscoverer(s) – Identify the scientist or research team credited with its discovery.\nDiscovery Location – Mention the country, laboratory, university, or research facility where the discovery took place.\nOrganization or Institution – Highlight the university, laboratory, scientific organization, or research institution involved in its discovery.\nDiscovery Background – Provide a brief but informative explanation of how the element was discovered, synthesized, or isolated.\nHistorical Significance – Explain why the discovery was important to the development of chemistry and the periodic table.\n\nPoster Design and Visual Presentation\n\nUse a chronological timeline layout, arranging all ten elements in the correct historical sequence. Make the timeline visually prominent, with clear dates, connecting lines, and distinct information sections for every element. Incorporate scientifically relevant illustrations, laboratory imagery, historical photographs of discoverers, and visual representations of the elements where appropriate. Use a distinct color scheme for each element while maintaining a consistent and professional overall design. Include small periodic-table-style element boxes containing the atomic number, chemical symbol, and element name. Use informative icons and visual markers to represent scientists, research institutions, laboratories, and discovery locations. Establish a clear visual hierarchy using bold headings, readable typography, organized text, and balanced spacing.\n\nAdditional Requirements\n\nEnsure all historical information, discovery dates, scientist names, and institutional affiliations are factually accurate. Distinguish between the initial discovery, first isolation, synthesis, and official recognition of an element whenever these occurred in different years. For elements discovered through international collaborations, identify the participating research institutions and countries. Avoid overcrowding the poster while retaining meaningful scientific and historical details. Include a short introductory section explaining the importance of element discovery in the history of chemistry. Add a brief concluding section highlighting how scientific collaboration and technological advancement contributed to the discovery of these elements. Include credible references or sources at the bottom of the poster.\n\nOverall Style\n\nThe final output should resemble a professional science exhibition or university-level educational infographic: visually attractive, historically informative, academically reliable, and easy to understand. Make the poster detailed enough for an academic presentation or classroom exhibit, with an engaging chronological storytelling approach that connects each element's discovery to the scientists, laboratories, and organizations responsible for advancing our understanding of the periodic table.\n\nsvg";

test('recognizes the exact operator assignment prompt', () => {
  assert.ok(operatorBrief.length > 2400);
  assert.equal(extractExplicitPosterGenerationPrompt(operatorBrief), operatorBrief.replace(/\s+/g, ' ').trim());
});


const redesignContext = `Operator: ${operatorBrief}\nJARVIS: The poster was generated and displayed.\nOperator: try generating a different design\nJARVIS: Previous layout description.`;

test('routes “try generating a different design” back through poster generation', () => {
  const result = extractContextualPosterRedesignRequest(
    'try generating a different design', redesignContext, operatorBrief, 'cards',
  );
  assert.ok(result);
  assert.notEqual(result.designVariant, 'cards');
  assert.ok(['cards', 'timeline', 'orbit', 'blueprint', 'museum', 'fieldnotes', 'collage'].includes(result.designVariant));
  assert.match(result.prompt, /ORIGINAL OPERATOR BRIEF TO PRESERVE/);
  assert.ok(result.prompt.includes('Mendelevium'));
  assert.equal(result.sourcePrompt, operatorBrief);
});


test('selects new compositions from the expanded set without repeating recent families', () => {
  const recent = ['cards', 'timeline', 'orbit', 'blueprint'];
  const result = extractContextualPosterRedesignRequest(
    'try generating a different design', redesignContext, operatorBrief, 'blueprint', recent,
  );
  assert.ok(result);
  assert.equal(result.operation, 'redesign');
  assert.ok(!recent.slice(-4).includes(result.designVariant));
  assert.notEqual(result.designVariant, 'blueprint');
});

test('routes “nono start from scratch and create a different one” as a new poster job', () => {
  const result = extractContextualPosterRedesignRequest(
    'nono start from scratch and create a different one]', redesignContext, operatorBrief, 'timeline',
  );
  assert.ok(result);
  assert.notEqual(result.designVariant, 'timeline');
  assert.ok(result.prompt.includes('Tennessine'));
  assert.match(result.prompt, /Do not copy the previous composition/);
  assert.equal(result.sourcePrompt, operatorBrief);
});

test('refines the current design for visual additions and artsy directions', () => {
  const cases = [
    ['try something with more visuals', 'refine', 'high'],
    ['try something artsy', 'refine', 'high'],
    ['now put some design element on the empty spaces', 'refine', 'high'],
    ['make the empty spaces more interesting with scientific illustrations', 'refine', 'high'],
  ];
  for (const [prompt, operation, density] of cases) {
    const result = extractContextualPosterRedesignRequest(prompt, redesignContext, operatorBrief, 'timeline', ['cards', 'timeline']);
    assert.ok(result, prompt);
    assert.equal(result.operation, operation, prompt);
    assert.equal(result.designVariant, 'timeline', prompt);
    assert.equal(result.visualDensity, density, prompt);
  }
});

test('creates a new composition while preserving content when explicitly asked', () => {
  const cases = [
    'generate a new one, same content but a very different design, with artsy elements on empty spaces',
    'nono start from scratch and create a different one]',
    'give me one then',
  ];
  for (const prompt of cases) {
    const result = extractContextualPosterRedesignRequest(prompt, redesignContext, operatorBrief, 'timeline', ['cards', 'timeline', 'orbit']);
    assert.ok(result, prompt);
    assert.equal(result.operation, 'redesign', prompt);
    assert.notEqual(result.designVariant, 'timeline', prompt);
    assert.equal(result.sourcePrompt, operatorBrief);
  }
});

test('does not mistake an ordinary design question for a poster regeneration request', () => {
  assert.equal(extractContextualPosterRedesignRequest('What makes a different design effective?', redesignContext, operatorBrief), null);
});


test('identifies fabricated text-only claims that an image was rendered', () => {
  assert.equal(isUnverifiedImageCreationClaim('New design created locally: horizontal timeline flow, modern infographic style.'), true);
  assert.equal(isUnverifiedImageCreationClaim('Rendered locally with a new layout and enhanced lab imagery.'), true);
  assert.equal(isUnverifiedImageCreationClaim('I can create a new poster after you provide a subject.'), false);
  assert.equal(isUnverifiedImageCreationClaim('The referenced PNG is no longer available in the local archive.'), false);
});


test('keeps the original brief stable across repeated poster redesigns', () => {
  const first = extractContextualPosterRedesignRequest('try generating a different design', redesignContext, operatorBrief, 'cards');
  assert.ok(first);
  const second = extractContextualPosterRedesignRequest('start from scratch and create a different one', redesignContext, first.prompt, first.designVariant);
  assert.ok(second);
  assert.equal(second.sourcePrompt, operatorBrief);
  assert.ok(second.prompt.includes('Tennessine'));
  assert.ok(!second.sourcePrompt.includes('REDESIGN AN EXISTING EDUCATIONAL POSTER'));
});


test('routes general image requests even when the chat contains an earlier poster', () => {
  assert.equal(extractImageGenerationPrompt('now generate an image of a robot'), 'a robot');
  assert.equal(extractImageGenerationPrompt('make me a picture of a realistic robot'), 'a realistic robot');
  assert.equal(extractImageGenerationPrompt('make a me picture of a realistic robot'), 'a realistic robot');
  assert.equal(extractImageGenerationPrompt('1+1'), null);
});

test('detects explicit landscape and portrait canvas constraints', () => {
  assert.equal(extractRequestedVisualOrientation('Create a highly detailed LANDSCAPE-ORIENTATION educational poster.'), 'landscape');
  assert.equal(extractRequestedVisualOrientation('Make me a new poster, 16:9 landscape format.'), 'landscape');
  assert.equal(extractRequestedVisualOrientation('Make it landscape.'), 'landscape');
  assert.equal(extractRequestedVisualOrientation('Use portrait orientation.'), 'portrait');
  assert.equal(extractRequestedVisualOrientation('Create a painting of a mountain landscape.'), null);
});

test('new poster refinements recognize education-focused design direction', () => {
  const result = extractContextualPosterRedesignRequest(
    'something with more educational design', redesignContext, operatorBrief, 'cards', [], 'portrait',
  );
  assert.ok(result);
  assert.equal(result.operation, 'refine');
  assert.equal(result.orientation, 'portrait');
  assert.equal(result.sourcePrompt, operatorBrief);
});

test('new poster variants inherit or explicitly change the last orientation', () => {
  const inherited = extractContextualPosterRedesignRequest(
    'give me a new one', redesignContext, operatorBrief, 'cards', [], 'landscape',
  );
  assert.ok(inherited);
  assert.equal(inherited.operation, 'redesign');
  assert.equal(inherited.orientation, 'landscape');

  const explicit = extractContextualPosterRedesignRequest(
    'new one, landscape format', redesignContext, operatorBrief, 'cards', [], 'portrait',
  );
  assert.ok(explicit);
  assert.equal(explicit.operation, 'redesign');
  assert.equal(explicit.orientation, 'landscape');

  const sameSubject = extractContextualPosterRedesignRequest(
    'make me a new poster about the same elements but make it landscape', redesignContext, operatorBrief, 'cards', [], 'portrait',
  );
  assert.ok(sameSubject);
  assert.equal(sameSubject.operation, 'redesign');
  assert.equal(sameSubject.orientation, 'landscape');
});

test('stop and cancel commands are classified as controls, not model prompts', () => {
  for (const prompt of ['stop', 'stop generation', 'stop image generation', 'cancel that', 'please stop listening', 'stop talking', 'pause the current task']) {
    assert.equal(isStopCommand(prompt), true, prompt);
  }
  assert.equal(isStopCommand('restart JARVIS'), false);
  assert.equal(isStopCommand('1+1'), false);
});


test('normalizes nullable and invalid saved orientations before restoring ChatLine state', () => {
  assert.equal(normalizeVisualOrientation('portrait'), 'portrait');
  assert.equal(normalizeVisualOrientation('landscape'), 'landscape');
  assert.equal(normalizeVisualOrientation(null), undefined);
  assert.equal(normalizeVisualOrientation(undefined), undefined);
  assert.equal(normalizeVisualOrientation('square'), undefined);
});
