import assert from 'node:assert/strict';

globalThis.window = {
  location: { hostname: 'localhost', origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
  talentscopeGetAuthToken: async () => 'learning-workspace-token'
};
const localStore = new Map();
globalThis.localStorage = {
  getItem: (k) => localStore.get(k) ?? null,
  setItem: (k, v) => localStore.set(k, String(v)),
  removeItem: (k) => localStore.delete(k),
  clear: () => localStore.clear()
};
globalThis.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.document = {};

const {
  loadLearningResources, loadLearningVideos, loadLearningActivityProgress,
  updateLearningActivityProgress, loadLearningCurriculum, recordLearningChapterEvent
} = await import('../src/api/learning-client.js');
const {
  renderResourceCard, renderActiveChapterWorkspace, renderDedicatedLessonWorkspace,
  extractLearningVideoId, isValidLearningVideoRecord, buildLearningThumbnailUrl,
  revealLearningThumbnailFallback, getTopicLessonContent, renderPersonalizedRoadmap,
  getChapterAssessmentData, getTopicKnowledgeCheck, setupProctoringListeners, cleanupProctoringListeners,
  isChapterLockedByProctor, renderMalpracticeLockoutModal, TOPIC_VIDEO_MAP,
  renderDetailedProgressModal, renderDedicatedProgressSection,
  renderProctorPenaltyModal, getCompletedCoursesHistory, recordCompletedCourse,
  renderRoadmapWizardModal
} = await import('../src/pages/individual/learning/Learning.js');
const { ALL_MCQ_BANKS } = await import('../src/pages/individual/learning/learning-assessment-bank.js');
const originalFetch = globalThis.fetch;
try {
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ resources: [], count: 0 });
  };
  await loadLearningResources({ skillId: 'python' });
  assert.match(request.url, /\/api\/v1\/learning\/resources\?limit=20&skill_id=python/);
  assert.equal(request.options.headers.Authorization, 'Bearer learning-workspace-token');

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ videos: [], fallback: { verification_status: 'unverified_search_results' }, count: 0 });
  };
  const videos = await loadLearningVideos({ skillId: 'ui_ux' });
  assert.match(request.url, /\/api\/v1\/learning\/videos\?/);
  assert.equal(videos.fallback.verification_status, 'unverified_search_results');

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ activities: [], count: 0 });
  };
  await loadLearningActivityProgress();
  assert.match(request.url, /\/api\/v1\/learning\/progress$/);
  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ curriculum: null });
  };
  await loadLearningCurriculum();
  assert.match(request.url, /\/api\/v1\/learning\/curriculum$/);
  assert.equal(request.options.headers.Authorization, 'Bearer learning-workspace-token');
  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ curriculum: null });
  };
  await recordLearningChapterEvent('chapter-a1b2', { event_id: 'event-id', event_type: 'chapter_started' });
  assert.match(request.url, /\/api\/v1\/learning\/chapters\/chapter-a1b2\/events$/);
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.headers.Authorization, 'Bearer learning-workspace-token');
  assert.equal(JSON.parse(request.options.body).event_type, 'chapter_started');
  await updateLearningActivityProgress('github-skills', 'completed');
  assert.equal(request.options.method, 'PUT');
  assert.deepEqual(JSON.parse(request.options.body), { status: 'completed' });
  assert.equal(request.options.headers.Authorization, 'Bearer learning-workspace-token');
  assert.throws(() => updateLearningActivityProgress('github-skills', 'watched'), /Invalid learning activity status/);
  const unknownProgress = renderResourceCard({
    resource_id: 'github-skills', title: 'GitHub Skills', url: 'https://learn.github.com/',
    resource_type: 'practice', provider: 'GitHub', verification_status: 'verified_official'
  });
  assert.match(unknownProgress, /Status unknown/);
  assert.doesNotMatch(unknownProgress, /Mark in progress/);
  const video = renderResourceCard({
    video_id: 'jS4aFq5-91M', title: 'C Programming Course', channel_name: 'freeCodeCamp.org',
    url: 'https://www.youtube.com/watch?v=jS4aFq5-91M', verification_status: 'verified_youtube_listing',
    provenance: 'Catalog record', license_attribution: 'YouTube', skill_ids: ['c']
  }, { video: true });
  assert.match(video, /i\.ytimg\.com\/vi\/jS4aFq5-91M\/hqdefault\.jpg/);
  assert.match(video, /https:\/\/www\.youtube\.com\/watch\?v=jS4aFq5-91M/);
  assert.match(video, /Video thumbnail unavailable/);
  assert.match(video, /freeCodeCamp\.org/);
  const invalidVideo = renderResourceCard({
    video_id: 'fake-id', title: 'Untrusted', channel_name: 'Unknown',
    url: 'https://www.youtube.com/watch?v=somebodyelses', verification_status: 'verified_youtube_listing'
  }, { video: true });
  assert.doesNotMatch(invalidVideo, /ytimg/);
  const fallbackNode = { hidden: true };
  const failedImage = { hidden: false, parentElement: { querySelector: selector => selector === '.lp-video-thumbnail-fallback' ? fallbackNode : null } };
  revealLearningThumbnailFallback(failedImage);
  assert.equal(failedImage.hidden, true);
  assert.equal(fallbackNode.hidden, false);

  const chapterHtml = renderActiveChapterWorkspace({
    chapter_id: 'chapter-0123456789abcdef0123', title: 'C fundamentals', status: 'in_progress',
    objective: 'Practice C fundamentals.', learning_objectives: ['Write a small C program.'],
    resources: [], resource_required: false, practice_activity: 'Write and run a small C program.',
    completion_policy: 'Submit the reflection.', assessment_checkpoint: { status: 'unavailable' },
    progress: { status: 'in_progress', events: [], resources: [] }
  }, [{ chapter_id: 'chapter-0123456789abcdef0123', status: 'in_progress' }]);
  assert.match(chapterHtml, /Back to My Learning/);
  assert.match(chapterHtml, /Write a small C program/);
  assert.match(chapterHtml, /No verified learning resource is currently available/);
  assert.match(chapterHtml, /Save reflection/);
  assert.match(chapterHtml, /Questions are awaiting human review/);
  assert.doesNotMatch(chapterHtml, /UI\/UX Designer|job applications/);
  assert.doesNotMatch(chapterHtml, /Chapter complete/);

  // --- Video validation and thumbnail tests ---
  assert.equal(buildLearningThumbnailUrl('jS4aFq5-91M', 'https://www.youtube.com/watch?v=jS4aFq5-91M'), 'https://i.ytimg.com/vi/jS4aFq5-91M/hqdefault.jpg');
  assert.equal(buildLearningThumbnailUrl(null, 'https://www.youtube.com/watch?v=jS4aFq5-91M'), null);
  assert.equal(buildLearningThumbnailUrl(undefined, 'https://www.youtube.com/watch?v=jS4aFq5-91M'), null);
  assert.equal(buildLearningThumbnailUrl('bad_id', 'https://www.youtube.com/watch?v=bad_id'), null);
  assert.equal(buildLearningThumbnailUrl('jS4aFq5-91M', 'https://www.youtube.com/results?search_query=c+tutorial'), null);
  assert.equal(buildLearningThumbnailUrl('jS4aFq5-91M', 'https://evil.example.com/watch?v=jS4aFq5-91M'), null);

  assert.equal(extractLearningVideoId({ video_id: 'jS4aFq5-91M' }), 'jS4aFq5-91M');
  assert.equal(extractLearningVideoId({ activity_id: 'youtube-dX8396ZmSPk' }), 'dX8396ZmSPk');
  assert.equal(extractLearningVideoId({ resource_id: 'youtube-HXV3zeQKqGY' }), 'HXV3zeQKqGY');
  assert.equal(extractLearningVideoId({ url: 'https://www.youtube.com/watch?v=0sOvCWFmrtA' }), '0sOvCWFmrtA');
  assert.equal(extractLearningVideoId({ resource_id: 'youtube-search-c', url: 'https://www.youtube.com/results?search_query=C+tutorial' }), null);
  assert.equal(extractLearningVideoId(null), null);

  // --- Search fallback resource card test ---
  const searchCard = renderResourceCard({
    resource_id: 'youtube-search-c', title: 'YouTube search results for C',
    url: 'https://www.youtube.com/results?search_query=C+tutorial',
    resource_type: 'video_search', provider: 'YouTube',
    verification_status: 'unverified_search_results'
  }, { searchable: true });
  assert.match(searchCard, /Search results · not verified/);
  assert.doesNotMatch(searchCard, /<img/);
  assert.doesNotMatch(searchCard, /undefined/);
  assert.doesNotMatch(searchCard, /ytimg/);

  // --- Dedicated Lesson Workspace: Curated Video Lesson ---
  const curatedLessonHtml = renderDedicatedLessonWorkspace({
    milestone_id: 'milestone-js-fundamentals', sequence: 1,
    title: 'JavaScript Fundamentals', explanation: 'Understand JavaScript syntax and runtime.',
    learning_objectives: ['Learn variables and functions', 'Understand closures'],
    skill_id: 'javascript', skill_name: 'JavaScript',
    resources: [{
      resource_id: 'youtube-jS4aFq5-91M', title: 'JavaScript Programming - Full Course',
      url: 'https://www.youtube.com/watch?v=jS4aFq5-91M', provider: 'freeCodeCamp.org',
      resource_type: 'video', verification_status: 'verified_youtube_listing'
    }],
    practice_activity: 'Write a small script.'
  }, {
    title: 'JavaScript Mastery', milestones: [{ milestone_id: 'milestone-js-fundamentals', title: 'JavaScript Fundamentals' }]
  }, { assessments: [] });

  assert.match(curatedLessonHtml, /lp-lesson-video-box/);
  assert.match(curatedLessonHtml, /https:\/\/i\.ytimg\.com\/vi\/jS4aFq5-91M\/hqdefault\.jpg/);
  assert.match(curatedLessonHtml, /Curated Video/);
  assert.match(curatedLessonHtml, /Video thumbnail unavailable/);
  assert.doesNotMatch(curatedLessonHtml, /undefined/);

  // --- Dedicated Lesson Workspace: Uncataloged Skill (COBOL) with Search Fallback ---
  const cobolLessonHtml = renderDedicatedLessonWorkspace({
    milestone_id: 'milestone-cobol-basics', sequence: 1,
    title: 'COBOL Paragraphs', explanation: 'Understand COBOL divisions and paragraphs.',
    learning_objectives: ['Declare paragraphs'],
    skill_id: 'cobol', skill_name: 'COBOL',
    resources: [{
      resource_id: 'youtube-search-cobol', title: 'YouTube search results for COBOL',
      url: 'https://www.youtube.com/results?search_query=COBOL+tutorial',
      provider: 'YouTube', resource_type: 'video_search',
      verification_status: 'unverified_search_results'
    }],
    practice_activity: 'Write a COBOL paragraph.'
  }, {
    title: 'COBOL Legacy Systems', milestones: [{ milestone_id: 'milestone-cobol-basics', title: 'COBOL Paragraphs' }]
  }, { assessments: [], videoSearchFallbacks: [] });

  assert.match(cobolLessonHtml, /lp-lesson-search-fallback-card/);
  assert.match(cobolLessonHtml, /YouTube Search Suggestion/);
  assert.match(cobolLessonHtml, /Search YouTube ↗/);
  assert.match(cobolLessonHtml, /https:\/\/www\.youtube\.com\/results\?search_query=COBOL\+tutorial/);
  // Absolutely no broken images or undefined URLs!
  assert.doesNotMatch(cobolLessonHtml, /<img/);
  assert.doesNotMatch(cobolLessonHtml, /ytimg/);
  assert.doesNotMatch(cobolLessonHtml, /undefined/);
  assert.doesNotMatch(cobolLessonHtml, /lp-video-play/);

  // --- Dedicated Lesson Workspace: C Programming Topic 0 resolves C Intro Video from TOPIC_VIDEO_MAP ---
  const cTopic0Html = renderDedicatedLessonWorkspace({
    milestone_id: 'milestone-c-intro', sequence: 1,
    title: 'What Is C Programming?', explanation: 'Introduction to C language.',
    learning_objectives: ['Understand C compilation and structure'],
    skill_id: 'c', skill_name: 'C',
    resources: [{
      resource_id: 'youtube-search-c', title: 'YouTube search results for C',
      url: 'https://www.youtube.com/results?search_query=C+tutorial',
      provider: 'YouTube', resource_type: 'video_search',
      verification_status: 'unverified_search_results'
    }],
    practice_activity: 'Write your first C program.'
  }, {
    title: 'C Programming', milestones: [{ milestone_id: 'milestone-c-intro', title: 'What Is C Programming?' }]
  }, { assessments: [], activeTopicIdx: 0 });

  assert.match(cTopic0Html, /lp-lesson-video-box/);
  assert.match(cTopic0Html, /KJgsSFOSQv0/);

  // --- Dedicated Lesson Workspace: Documentation only ---
  const docLessonHtml = renderDedicatedLessonWorkspace({
    milestone_id: 'milestone-python-docs', sequence: 1,
    title: 'Python Standard Library', explanation: 'Read standard library modules.',
    learning_objectives: ['Explore sys and os'],
    skill_id: 'python', skill_name: 'Python',
    resources: [{
      resource_id: 'python-docs-stdlib', title: 'The Python Standard Library',
      url: 'https://docs.python.org/3/library/', provider: 'Python Software Foundation',
      resource_type: 'documentation', verification_status: 'verified_official'
    }],
    practice_activity: 'Read standard library docs.'
  }, {
    title: 'Python Deep Dive', milestones: [{ milestone_id: 'milestone-python-docs', title: 'Python Standard Library' }]
  }, { assessments: [] });

  assert.match(docLessonHtml, /lp-lesson-docs-section/);
  assert.match(docLessonHtml, /The Python Standard Library/);
  assert.doesNotMatch(docLessonHtml, /ytimg/);
  assert.doesNotMatch(docLessonHtml, /undefined/);

  // --- Dedicated Lesson Workspace: No Resources Available ---
  const emptyLessonHtml = renderDedicatedLessonWorkspace({
    milestone_id: 'milestone-no-res', sequence: 1,
    title: 'Theoretical Concepts', explanation: 'Abstract thinking task.',
    learning_objectives: ['Ponder algorithm complexity'],
    skill_id: null, skill_name: 'Theory',
    resources: [],
    practice_activity: 'Draft algorithm analysis on paper.'
  }, {
    title: 'Theory Roadmap', milestones: [{ milestone_id: 'milestone-no-res', title: 'Theoretical Concepts' }]
  }, { assessments: [] });

  assert.match(emptyLessonHtml, /No verified learning resource is currently available for this topic/);
  assert.match(emptyLessonHtml, /Theoretical Concepts/);
  assert.doesNotMatch(emptyLessonHtml, /<img/);
  assert.doesNotMatch(emptyLessonHtml, /undefined/);

  // --- Phase 3: Real Topic Completion, Navigation & Drawer Synchronization Tests ---
  const multiMilestoneRoadmap = {
    title: 'Multi-Topic Roadmap',
    milestones: [
      { milestone_id: 'm-1', sequence: 1, title: 'Topic One', status: 'not_started' },
      { milestone_id: 'm-2', sequence: 2, title: 'Topic Two', status: 'not_started' },
      { milestone_id: 'm-3', sequence: 3, title: 'Topic Three', status: 'not_started' }
    ]
  };

  // 1. Initial State: viewing Topic One (not completed)
  const initialWorkspace = renderDedicatedLessonWorkspace(
    multiMilestoneRoadmap.milestones[0],
    multiMilestoneRoadmap,
    { assessments: [] }
  );

  // Previous Lesson must be disabled on first topic
  assert.match(initialWorkspace, /data-navigate-lesson="" disabled aria-disabled="true"/);
  assert.match(initialWorkspace, /First lesson reached/);

  // Next Lesson must be disabled because Topic One is not completed
  assert.match(initialWorkspace, /data-navigate-lesson="" disabled aria-disabled="true"/);
  assert.match(initialWorkspace, /Complete the current topic to unlock next lesson/);

  // Completion button must show "Mark Topic as Complete"
  assert.match(initialWorkspace, /Mark Topic as Complete/);
  assert.match(initialWorkspace, /id="lpMarkLessonCompleteBtn"/);

  // Drawer: Topic One is active, Topic Two & Three are locked
  assert.match(initialWorkspace, /class="lp-curriculum-topic-btn is-active\s*" data-navigate-lesson="m-1"/);
  assert.match(initialWorkspace, /class="lp-curriculum-topic-btn\s*is-locked" data-navigate-lesson="m-2" disabled aria-disabled="true"/);
  assert.match(initialWorkspace, /class="lp-curriculum-topic-btn\s*is-locked" data-navigate-lesson="m-3" disabled aria-disabled="true"/);
  assert.match(initialWorkspace, /Complete previous topics to unlock \(Topic Two\)/);

  // 2. Completed State: Topic One completed, viewing Topic One
  const completedM1Roadmap = {
    title: 'Multi-Topic Roadmap',
    milestones: [
      { milestone_id: 'm-1', sequence: 1, title: 'Topic One', status: 'completed' },
      { milestone_id: 'm-2', sequence: 2, title: 'Topic Two', status: 'in_progress' },
      { milestone_id: 'm-3', sequence: 3, title: 'Topic Three', status: 'not_started' }
    ]
  };

  const completedWorkspace = renderDedicatedLessonWorkspace(
    completedM1Roadmap.milestones[0],
    completedM1Roadmap,
    { assessments: [] }
  );

  // Completion gate reflects completion
  assert.match(completedWorkspace, /Topic Completed ✓/);
  assert.match(completedWorkspace, /class="lp-btn-success"/);
  assert.match(completedWorkspace, /disabled/);

  // Next Lesson is now enabled pointing to m-2
  assert.match(completedWorkspace, /data-navigate-lesson="m-2"/);
  assert.doesNotMatch(completedWorkspace, /data-navigate-lesson="m-2"\s*disabled/);

  // Drawer: Topic One has checkmark, Topic Two is unlocked & available, Topic Three remains locked
  assert.match(completedWorkspace, /is-completed/);
  assert.match(completedWorkspace, /data-navigate-lesson="m-2"/);
  assert.doesNotMatch(completedWorkspace, /is-locked[^>]*data-navigate-lesson="m-2"/);
  assert.match(completedWorkspace, /is-locked[^>]*data-navigate-lesson="m-3"/);

  // 3. Navigated State: viewing Topic Two
  const topicTwoWorkspace = renderDedicatedLessonWorkspace(
    completedM1Roadmap.milestones[1],
    completedM1Roadmap,
    { assessments: [] }
  );

  // Previous button is enabled pointing to m-1
  assert.match(topicTwoWorkspace, /data-navigate-lesson="m-1"/);
  assert.doesNotMatch(topicTwoWorkspace, /data-navigate-lesson="m-1"\s*disabled/);

  // Drawer: Topic One is is-completed (clickable to revisit), Topic Two is is-active
  assert.match(topicTwoWorkspace, /class="lp-curriculum-topic-btn\s*is-completed\s*" data-navigate-lesson="m-1"/);
  assert.match(topicTwoWorkspace, /class="lp-curriculum-topic-btn is-active\s*" data-navigate-lesson="m-2"/);

  // --- Week Accordion Array Expansion & Curriculum Hierarchy Tests ---
  const roadmapForAccordion = {
    title: 'C Systems Programming',
    summary: 'Build progressive systems programming capability in C.',
    target_duration_days: 30,
    milestones: [
      { milestone_id: 'm-c1', sequence: 1, title: 'C Fundamentals', learning_objectives: ['Data Types', 'Variables'], skill_name: 'C' },
      { milestone_id: 'm-c2', sequence: 2, title: 'Control Flow', learning_objectives: ['Conditionals', 'Loops'], skill_name: 'C' },
      { milestone_id: 'm-c3', sequence: 3, title: 'Functions', learning_objectives: ['Call by value', 'Prototypes'], skill_name: 'C' },
      { milestone_id: 'm-c4', sequence: 4, title: 'Pointers & Memory', learning_objectives: ['Memory Addresses', 'Pointer Arithmetic'], skill_name: 'C' },
      { milestone_id: 'm-c5', sequence: 5, title: 'Structures', learning_objectives: ['Struct declarations', 'Typedef'], skill_name: 'C' }
    ]
  };

  // Week 2 expanded via array [2]
  const weekTwoExpandedHtml = renderPersonalizedRoadmap({ personalizedRoadmap: roadmapForAccordion, expandedWeeks: [2] });
  assert.match(weekTwoExpandedHtml, /is-expanded"[^>]*data-week-number="2"/);
  assert.doesNotMatch(weekTwoExpandedHtml, /is-expanded"[^>]*data-week-number="1"/);
  assert.match(weekTwoExpandedHtml, /Topic 1/);
  assert.match(weekTwoExpandedHtml, /Chapter Assessment/);
  // Clutter headings explicitly ordered removed in Phase 2
  assert.doesNotMatch(weekTwoExpandedHtml, /Chapter Curriculum Hierarchy/);
  assert.doesNotMatch(weekTwoExpandedHtml, /Platform-generated practice guidance/);

  // --- Topic-Specific Educational Content Tests ---
  const cPointerContent = getTopicLessonContent({ skill_name: 'C' }, 'Pointer Arithmetic & Memory', 0);
  assert.match(cPointerContent.concept, /Pointers in C/);
  assert.match(cPointerContent.code, /#include <stdio\.h>/);
  assert.match(cPointerContent.output, /Before Swap:/);
  assert.match(cPointerContent.explanation, /dereference operator/);

  const pyContent = getTopicLessonContent({ skill_name: 'Python' }, 'Data Structures', 0);
  assert.match(pyContent.code, /def process_metrics/);
  assert.match(pyContent.output, /Computed Metrics:/);

  // --- Phase 2: Dedicated Topic View does NOT embed compiler clutter ---
  const workspaceTopicView = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[3],
    roadmapForAccordion,
    { assessments: [] }
  );
  assert.doesNotMatch(workspaceTopicView, /lp-coding-workspace-card/);

  // --- Phase 2: Dedicated Chapter Assessment View embeds Secure Coding Sandbox ---
  // --- Two-Stage Chapter Assessment View: Stage 1 (MCQs) and Stage 2 (Coding Sandbox) ---
  const workspaceStage1 = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[3],
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      chapterAssessmentActive: true,
      assessmentStage: 'stage1_mcq',
      completedTopics: { 'm-c4': [0, 1] },
      assessments: []
    }
  );
  assert.match(workspaceStage1, /STAGE 1 OF 2: OBJECTIVE ASSESSMENT/);
  assert.match(workspaceStage1, /id="lpFinishMcqSectionBtn"/);

  const workspaceWithCompiler = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[3],
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      chapterAssessmentActive: true,
      assessmentStage: 'stage2_coding',
      completedTopics: { 'm-c4': [0, 1] },
      assessments: []
    }
  );
  assert.match(workspaceWithCompiler, /lp-coding-workspace-card/);
  assert.match(workspaceWithCompiler, /lp-code-editor-textarea/);
  assert.match(workspaceWithCompiler, /id="lpAssessmentRunCodeBtn"/);
  assert.match(workspaceWithCompiler, /id="lpAssessmentResetCodeBtn"/);
  assert.match(workspaceWithCompiler, /lp-compiler-notice-card/);
  assert.match(workspaceWithCompiler, /Isolated Process Execution/);
  assert.match(workspaceWithCompiler, /STAGE 2 OF 2: CODING SANDBOX EVALUATION/);
  assert.match(workspaceWithCompiler, /lp-coding-split-layout/);

  // --- Phase 2: Coursera-style Multi-Topic Navigation & Decoupled Chapter Assessment Gate Tests ---
  // Intermediate topic (Topic 0 of 2): Chapter Assessment Gate must NOT be rendered on intermediate topic
  const multiTopicMilestone = roadmapForAccordion.milestones[3]; // 'Pointers & Memory', objectives: ['Memory Addresses', 'Pointer Arithmetic']
  const intermediateTopicWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    { activeTopicIndex: 0, assessments: [] }
  );
  assert.match(intermediateTopicWorkspace, /TOPIC 1 OF 2/);
  assert.match(intermediateTopicWorkspace, /Memory Addresses/);
  assert.match(intermediateTopicWorkspace, /Key Takeaways/);
  assert.match(intermediateTopicWorkspace, /lp-takeaways-box/);
  assert.match(intermediateTopicWorkspace, /Next Topic/);
  assert.match(intermediateTopicWorkspace, /data-select-topic="1"/);
  // Intermediate topic MUST NOT display the Chapter Assessment Gate card
  assert.doesNotMatch(intermediateTopicWorkspace, /CHAPTER ASSESSMENT GATE/);

  // Last topic (Topic 1 of 2):
  const lastTopicWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    { activeTopicIndex: 1, assessments: [] }
  );
  assert.match(lastTopicWorkspace, /TOPIC 2 OF 2/);
  assert.match(lastTopicWorkspace, /Pointer Arithmetic/);
  assert.match(lastTopicWorkspace, /Previous Topic/);
  assert.match(lastTopicWorkspace, /data-select-topic="0"/);
  assert.match(lastTopicWorkspace, /Proceed to Chapter Assessment →/);
  assert.match(lastTopicWorkspace, /data-select-topic="2"/);
  assert.doesNotMatch(lastTopicWorkspace, /CHAPTER ASSESSMENT GATE/);

  // Chapter Assessment Gate View (activeTopicIndex = 2):
  // When prerequisites not yet completed
  const prereqWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    { activeTopicIndex: 2, assessments: [] }
  );
  assert.match(prereqWorkspace, /PREREQUISITES REQUIRED/);
  assert.match(prereqWorkspace, /Chapter Topics Incomplete/);

  // When prerequisites completed -> Declaration Screen
  const declWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    { activeTopicIndex: 2, completedTopics: { 'm-c4': [0, 1] }, assessments: [] }
  );
  assert.match(declWorkspace, /CHAPTER ASSESSMENT GATE/);
  assert.match(declWorkspace, /Chapter 4 Assessment/);
  assert.match(declWorkspace, /id="lpStartChapterAssessmentBtn"/);

  // --- Multi-Skill Educational Content Generation Tests ---
  const jsContent = getTopicLessonContent({ skill_name: 'JavaScript' }, 'Async & Promises', 0);
  assert.match(jsContent.code, /syncTopicProgress/);
  assert.match(jsContent.output, /Progress synced:/);

  const uiuxContent = getTopicLessonContent({ skill_name: 'UI/UX Design' }, 'User Research & Personas', 0);
  assert.match(uiuxContent.concept, /User Research/);
  assert.equal(uiuxContent.code, null); // Truthful: non-programming domain does not fake code
  assert.ok(uiuxContent.takeaways.length >= 2);

  const softDevContent = getTopicLessonContent({ skill_name: 'Software Developer' }, 'System Architecture & Modularity', 0);
  assert.match(softDevContent.concept, /SOLID/);
  assert.match(softDevContent.code, /ProgressNotifier/);

  const aiContent = getTopicLessonContent({ skill_name: 'AI Engineer' }, 'Prompt Engineering & Context', 0);
  assert.match(aiContent.code, /systemPrompt/);
  assert.match(aiContent.output, /Evaluation Result: APPROVED/);

  // --- Specialized C Toolchain and First Program Lesson Content Tests ---
  const cToolchainContent = getTopicLessonContent({ skill_name: 'C' }, 'Install and configure GCC or Clang compiler', 0);
  assert.match(cToolchainContent.concept, /GNU Compiler Collection/);
  assert.ok(cToolchainContent.instructions.length >= 4);
  assert.match(cToolchainContent.code, /TalentScope C Toolchain/);
  assert.match(cToolchainContent.output, /Active & Verified/);
  assert.ok(cToolchainContent.common_mistakes.length >= 2);

  const cHelloWorldContent = getTopicLessonContent({ skill_name: 'C' }, 'Write, compile, and run your first Hello World in C', 1);
  assert.match(cHelloWorldContent.concept, /main\(\)/);
  assert.match(cHelloWorldContent.code, /int main\(void\)/);
  assert.match(cHelloWorldContent.code, /Hello, World! Welcome to C Systems Programming/);
  assert.match(cHelloWorldContent.output, /Hello, World!/);
  assert.ok(cHelloWorldContent.common_mistakes.length >= 2);

  // --- Assessment Scoring Integrity & State Separation Tests ---
  // 1. Unattempted assessment with prerequisites satisfied -> Declaration Screen only, NO score!
  const unattemptedWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    { activeTopicIndex: 2, completedTopics: { 'm-c4': [0, 1] }, assessments: [] }
  );
  assert.doesNotMatch(unattemptedWorkspace, /Benchmark Met/);
  assert.doesNotMatch(unattemptedWorkspace, /85% Score/);
  assert.doesNotMatch(unattemptedWorkspace, /Congratulations! Chapter 4 Verified/);
  assert.match(unattemptedWorkspace, /Start Assessment/);

  // 2. Failed assessment (< 70%): Shows actual calculated score percentage, NOT passed!
  const failedWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      completedTopics: { 'm-c4': [0, 1] },
      chapterAssessmentResult: { score: 10, max_score: 20, percentage: 50, passed: false },
      assessments: []
    }
  );
  assert.match(failedWorkspace, /Benchmark Not Met \(50% vs 70% Required\)/);
  assert.match(failedWorkspace, /Review Current Chapter/);
  assert.doesNotMatch(failedWorkspace, /Benchmark Met/);

  // 3. Passed assessment (>= 70%): Shows actual calculated score percentage, NOT hardcoded 85%!
  const passedWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      completedTopics: { 'm-c4': [0, 1] },
      chapterAssessmentResult: { score: 15, max_score: 20, percentage: 75, passed: true },
      assessments: []
    }
  );
  assert.match(passedWorkspace, /75% Score \(Benchmark Met\)/);
  assert.match(passedWorkspace, /Congratulations! Chapter 4 Verified/);
  assert.doesNotMatch(passedWorkspace, /85% Score/);

  // 4. Revisiting completed chapter without current session result -> Verified Chapter, NO fake score!
  const revisitedWorkspace = renderDedicatedLessonWorkspace(
    { ...multiTopicMilestone, status: 'completed' },
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      assessments: []
    }
  );
  assert.match(revisitedWorkspace, /Chapter 4 Verified ✓/);
  assert.match(revisitedWorkspace, /Verified Chapter/);
  assert.doesNotMatch(revisitedWorkspace, /85% Score/);

  // --- Video-First Layout Verification ---
  // In curated lesson workspace, the video walkthrough container must appear BEFORE educational concepts card
  assert.ok(curatedLessonHtml.includes('lp-topic-video-container'));
  assert.ok(curatedLessonHtml.includes('lp-lesson-concepts-card'));
  assert.ok(
    curatedLessonHtml.indexOf('lp-topic-video-container') < curatedLessonHtml.indexOf('lp-lesson-concepts-card'),
    'Video tutorial container must precede the educational concepts card for video-first presentation'
  );

  // --- Canonical 8 C Chapters Topic Content Tests ---
  const cCh1 = getTopicLessonContent({ skill_name: 'C' }, 'What Is C Programming? History and Design Philosophy', 0);
  assert.match(cCh1.concept, /Dennis Ritchie/);
  assert.ok(cCh1.takeaways.length >= 2);

  const cCh2 = getTopicLessonContent({ skill_name: 'C' }, 'printf and scanf Standard I/O', 3);
  assert.match(cCh2.code, /printf/);
  assert.match(cCh2.concept, /scanf/);
  assert.match(cCh2.output, /Receipt Summary/);

  const cCh3 = getTopicLessonContent({ skill_name: 'C' }, 'Conditionals: if, else-if, else and switch', 1);
  assert.match(cCh3.code, /if \(score >= 90\)/);
  assert.match(cCh3.concept, /switch/);
  assert.match(cCh3.output, /Final Grade: B/);

  const cCh4 = getTopicLessonContent({ skill_name: 'C' }, 'Function Declarations, Definitions and Headers', 0);
  assert.match(cCh4.code, /compute_sum/);
  assert.match(cCh4.output, /Sum of 14 \+ 28 = 42/);

  const cCh5 = getTopicLessonContent({ skill_name: 'C' }, 'Character Arrays and String Fundamentals', 1);
  assert.match(cCh5.code, /TalentScope/);
  assert.match(cCh5.output, /String content: TalentScope/);

  const cCh6 = getTopicLessonContent({ skill_name: 'C' }, 'Dynamic Memory Allocation (malloc, calloc, realloc, free)', 3);
  assert.match(cCh6.code, /malloc/);
  assert.match(cCh6.code, /free\(arr\)/);
  assert.match(cCh6.output, /Dynamic Array/);

  const cCh7 = getTopicLessonContent({ skill_name: 'C' }, 'Structures, Unions and Enumerations', 0);
  assert.match(cCh7.code, /StudentRecord/);
  assert.match(cCh7.output, /Direct access/);

  const cCh8 = getTopicLessonContent({ skill_name: 'C' }, 'Problem-Solving, Debugging and Code Quality', 0);
  assert.match(cCh8.code, /TalentScope C Engineering Capstone/);
  assert.match(cCh8.output, /zero compiler warnings/i);

  // --- Two-Stage Assessment Declaration & Scoring Breakdown Tests ---
  assert.match(declWorkspace, /Stage 1: Objective MCQs/);
  assert.match(declWorkspace, /30 Minutes \(5 Questions\)/);
  assert.match(declWorkspace, /Stage 2: Coding Sandbox/);
  assert.match(declWorkspace, /60 Minutes \(Server Evaluated\)/);
  assert.match(declWorkspace, /1 Sample \+ 5 Hidden Tests/);
  assert.match(declWorkspace, /≥ 70% Score Required/);
  assert.match(declWorkspace, /id="lpAssessmentAgreementCheck"/);
  assert.match(declWorkspace, /Sequential Stages/);
  assert.match(declWorkspace, /Focus Monitoring/);

  // Score breakdown verification on passed result card
  assert.match(passedWorkspace, /Stage 1 \(MCQs\):/);
  assert.match(passedWorkspace, /Stage 2 \(Coding\):/);
  assert.match(passedWorkspace, /Total: <strong>15 \/ 20 pts \(75%\)<\/strong>/);

  // --- Multi-Skill & Non-Coding Assessment Data Tests ---
  const javaData = getChapterAssessmentData({ skill_name: 'Java', title: 'Java Concurrency' });
  assert.match(javaData.title, /Java Enterprise Architecture/);
  assert.equal(javaData.coding.language, 'java');
  assert.equal(javaData.coding.question_id, 'ts-java-array-sum-001');

  const sqlData = getChapterAssessmentData({ skill_name: 'SQL', title: 'Advanced Queries' });
  assert.match(sqlData.title, /Relational Database Design/);
  assert.equal(sqlData.coding.language, 'sql');
  assert.equal(sqlData.coding.question_id, 'ts-sql-active-users-001');

  const htmlData = getChapterAssessmentData({ skill_name: 'HTML/CSS', title: 'Responsive Layouts' });
  assert.match(htmlData.title, /Frontend Web Architecture/);
  assert.equal(htmlData.mcqs.length, 30);

  const uxData = getChapterAssessmentData({ skill_name: 'UI/UX Design', title: 'Design System & Usability' });
  assert.equal(uxData.isCodingAppropriate, false);
  assert.match(uxData.practical_task.title, /Heuristic Usability Audit/);

  // --- Dedicated Assessment UI & Sidebar Suppression Tests ---
  const activeAssessmentWorkspace = renderDedicatedLessonWorkspace(
    multiTopicMilestone,
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      completedTopics: { 'm-c4': [0, 1] },
      chapterAssessmentActive: true,
      assessmentStage: 'stage1_mcq',
      chapterAssessmentTimer: 1800,
      chapterAssessmentAnswers: {}
    }
  );
  assert.match(activeAssessmentWorkspace, /is-assessment-mode/);
  assert.match(activeAssessmentWorkspace, /Proctoring Active · Controlled Assessment Session/);
  assert.doesNotMatch(activeAssessmentWorkspace, /lp-course-curriculum-col/);

  // Non-coding domain active assessment Stage 2 renders practical case analysis rather than code editor
  const uxActiveStage2 = renderDedicatedLessonWorkspace(
    { ...multiTopicMilestone, skill_name: 'UI/UX Design', title: 'Design System & Heuristics' },
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      completedTopics: { 'm-c4': [0, 1] },
      chapterAssessmentActive: true,
      assessmentStage: 'stage2_coding',
      chapterAssessmentTimer: 3600
    }
  );
  assert.match(uxActiveStage2, /STAGE 2 OF 2: PRACTICAL AUDIT &amp; SCENARIO EVALUATION/);
  assert.match(uxActiveStage2, /id="lpAssessmentCaseStudyInput"/);
  assert.doesNotMatch(uxActiveStage2, /id="lpAssessmentCodeEditor"/);

  // --- Prompt 2 Verification: 16:9 Video Embed Wrapper ---
  assert.match(curatedLessonHtml, /lp-lesson-video-embed-wrap/);
  assert.match(curatedLessonHtml, /lp-lesson-video-iframe/);
  assert.match(curatedLessonHtml, /youtube-nocookie\.com\/embed\/jS4aFq5-91M/);

  // --- Prompt 2 Verification: Three Distinct Code Sub-Cards ---
  const cLessonWorkspace = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[0],
    roadmapForAccordion,
    { activeTopicIndex: 0, assessments: [] }
  );
  assert.match(cLessonWorkspace, /lp-program-source-card/);
  assert.match(cLessonWorkspace, /lp-execution-output-card/);
  assert.doesNotMatch(cLessonWorkspace, /lp-code-walkthrough-card/);
  assert.doesNotMatch(cLessonWorkspace, /lp-course-tabs-bar/);
  assert.doesNotMatch(cLessonWorkspace, /📖 Deep Dive &amp; Guide|📖 Deep Dive & Guide/);
  assert.doesNotMatch(cLessonWorkspace, /lp-topic-mistakes-box/);
  assert.doesNotMatch(cLessonWorkspace, /lp-topic-exercise-box/);
  assert.match(cLessonWorkspace, /data-copy-code/);
  assert.match(cLessonWorkspace, /Process exited with code 0/);

  // --- Prompt 2 Verification: Non-programming domain omits code/terminal boxes ---
  const uxTopicWorkspace = renderDedicatedLessonWorkspace(
    { milestone_id: 'm-ux-1', title: 'Heuristic Evaluation', skill_name: 'UI/UX Design', learning_objectives: ['Analyze Usability'] },
    { title: 'UI/UX Design', milestones: [{ milestone_id: 'm-ux-1', title: 'Heuristic Evaluation' }] },
    { activeTopicIndex: 0, assessments: [] }
  );
  assert.doesNotMatch(uxTopicWorkspace, /lp-program-source-card/);
  assert.doesNotMatch(uxTopicWorkspace, /lp-execution-output-card/);
  assert.match(uxTopicWorkspace, /lp-concept-deep-dive/);

  // --- Prompt 2 Verification: Interactive Topic Knowledge Check and Completion Gating ---
  const unverifiedTopicWorkspace = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[0],
    roadmapForAccordion,
    { activeTopicIndex: 0, completedTopics: {}, topicKnowledgeCheckVerified: {}, assessments: [] }
  );
  assert.match(unverifiedTopicWorkspace, /lp-topic-knowledge-check-card/);
  assert.match(unverifiedTopicWorkspace, /name="lpTopicKcAnswer"/);
  assert.match(unverifiedTopicWorkspace, /id="lpCheckTopicAnswerBtn"/);
  // Mark complete button must be disabled when knowledge check is unverified
  assert.match(unverifiedTopicWorkspace, /id="lpMarkLessonCompleteBtn"[^>]*disabled aria-disabled="true"/);

  // When knowledge check is verified, mark complete button is enabled
  const verifiedTopicWorkspace = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[0],
    roadmapForAccordion,
    {
      activeTopicIndex: 0,
      completedTopics: {},
      topicKnowledgeCheckVerified: { 'm-c1_0': true },
      assessments: []
    }
  );
  assert.match(verifiedTopicWorkspace, /lp-kc-passed-badge/);
  assert.match(verifiedTopicWorkspace, /Topic Knowledge Verified/);
  assert.doesNotMatch(verifiedTopicWorkspace, /id="lpMarkLessonCompleteBtn"[^>]*disabled/);

  // --- Prompt 2 Verification: Fullscreen Assessment Header & Stage 2 Toolbar ---
  const activeAssessmentFullscreen = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[3],
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      completedTopics: { 'm-c4': [0, 1] },
      chapterAssessmentActive: true,
      assessmentStage: 'stage2_coding',
      chapterAssessmentTimer: 3600,
      editorTheme: 'dark',
      editorFontSize: '14px',
      customStdinEnabled: true,
      assessments: []
    }
  );
  assert.match(activeAssessmentFullscreen, /lp-assessment-fullscreen-header/);
  assert.match(activeAssessmentFullscreen, /id="lpExitAssessmentBtn"/);
  assert.match(activeAssessmentFullscreen, /Exit Assessment/);
  assert.match(activeAssessmentFullscreen, /lp-coding-questions-tabs/);
  assert.match(activeAssessmentFullscreen, /data-select-coding-q="0"/);
  assert.match(activeAssessmentFullscreen, /data-select-coding-q="1"/);
  assert.match(activeAssessmentFullscreen, /lp-coding-toolbar/);
  assert.match(activeAssessmentFullscreen, /id="lpAssessmentThemeToggleBtn"/);
  assert.match(activeAssessmentFullscreen, /id="lpAssessmentFontSizeSelect"/);
  assert.match(activeAssessmentFullscreen, /id="lpCustomStdinToggle"/);
  assert.match(activeAssessmentFullscreen, /id="lpAssessmentStdin"/);
  assert.match(activeAssessmentFullscreen, /id="lpAssessmentRunCodeBtn"/);
  assert.match(activeAssessmentFullscreen, /id="lpSubmitChapterAssessmentBtn"/);
  assert.doesNotMatch(activeAssessmentFullscreen, /id="lpAssessmentEvaluateAllBtn"/);

  // --- Prompt 2 Verification: Sidebar Lucide Icons ---
  assert.match(completedWorkspace, /data-lucide="circle"/);
  assert.match(completedWorkspace, /data-lucide="check-circle-2"/);
  assert.match(initialWorkspace, /data-lucide="lock"/);
  assert.match(initialWorkspace, /data-open-chapter-assessment/);

  // --- Prompt 2 Verification: Proctor Listeners Management ---
  assert.equal(typeof setupProctoringListeners, 'function');
  assert.equal(typeof cleanupProctoringListeners, 'function');
  cleanupProctoringListeners();

  // --- Prompt 3 & 4: 30-MCQ Assessment Bank Verification ---
  const expectedTracks = ['c', 'python', 'javascript', 'java', 'sql', 'html', 'design', 'general'];
  for (const track of expectedTracks) {
    const bank = ALL_MCQ_BANKS[track];
    assert.ok(Array.isArray(bank), `Track ${track} bank must be an array`);
    assert.equal(bank.length, 30, `Track ${track} must contain exactly 30 unique MCQs`);

    // Check answer distribution across opt-a, opt-b, opt-c, opt-d (~25% each)
    const counts = { 'opt-a': 0, 'opt-b': 0, 'opt-c': 0, 'opt-d': 0 };
    const ids = new Set();
    for (const q of bank) {
      assert.ok(!ids.has(q.id), `Duplicate MCQ ID in track ${track}: ${q.id}`);
      ids.add(q.id);
      assert.ok(counts[q.correct] !== undefined, `Valid correct option in ${q.id}`);
      counts[q.correct]++;
    }
    for (const opt of ['opt-a', 'opt-b', 'opt-c', 'opt-d']) {
      assert.ok(counts[opt] >= 5 && counts[opt] <= 10, `Option ${opt} in ${track} should be balanced (got ${counts[opt]})`);
    }
  }

  // --- Prompt 3 & 4: 3-Strike Proctoring Lockout & Malpractice Modal ---
  assert.equal(isChapterLockedByProctor('unknown-ch'), null);
  const fakeStorage = {};
  globalThis.localStorage = {
    getItem: (k) => fakeStorage[k] || null,
    setItem: (k, v) => { fakeStorage[k] = String(v); },
    removeItem: (k) => { delete fakeStorage[k]; }
  };
  const lockoutUntil = Date.now() + 86400000;
  localStorage.setItem('talentscope_lockout_m-c4', JSON.stringify({
    lockedUntil: lockoutUntil,
    reason: 'malpractice_proctoring_strikes'
  }));
  const lockedState = isChapterLockedByProctor('m-c4');
  assert.ok(lockedState);
  assert.equal(lockedState.lockedUntil, lockoutUntil);

  // Curriculum sidebar renders Flagged: 24h Cooldown badge for locked chapter
  const sidebarWithLockout = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[3],
    roadmapForAccordion,
    { activeTopicIndex: 0, assessments: [] }
  );
  assert.match(sidebarWithLockout, /Flagged: 24h Cooldown/);
  assert.match(sidebarWithLockout, /is-flagged-locked/);

  // Malpractice modal markup verification
  const modalClosed = renderMalpracticeLockoutModal({ malpracticeModalOpen: false });
  assert.equal(modalClosed, '');

  const modalOpen = renderMalpracticeLockoutModal({
    malpracticeModalOpen: true,
    malpracticeLockedUntil: lockoutUntil
  });
  assert.match(modalOpen, /lp-malpractice-lockout-modal/);
  assert.match(modalOpen, /Malpractice Lockout Enforced/);
  assert.match(modalOpen, /Assessment Terminated · 3 Strikes/);
  assert.match(modalOpen, /id="lpMalpracticeCountdown"/);
  assert.match(modalOpen, /id="lpDismissMalpracticeModalBtn"/);

  // --- Prompt 3 & 4: Varied Lesson Content (UI/UX Design Track) ---
  const uiuxLessonWorkspace = renderDedicatedLessonWorkspace(
    {
      milestone_id: 'm-uiux-1',
      title: 'Design Foundations',
      skill_name: 'UI/UX Design',
      learning_objectives: ['Wireframing & Hierarchy', 'User Heuristics']
    },
    {
      title: 'UI/UX Design Career Track',
      milestones: [{ milestone_id: 'm-uiux-1', title: 'Design Foundations', skill_name: 'UI/UX Design' }]
    },
    { activeTopicIndex: 0, assessments: [] }
  );
  assert.match(uiuxLessonWorkspace, /lp-design-case-study-card/);
  assert.match(uiuxLessonWorkspace, /lp-figma-workflow-card/);
  assert.match(uiuxLessonWorkspace, /lp-ux-checklist-card/);
  // Non-coding domain must NOT render code example or terminal output
  assert.doesNotMatch(uiuxLessonWorkspace, /lp-program-source-card/);
  assert.doesNotMatch(uiuxLessonWorkspace, /lp-execution-output-card/);

  // --- Prompt 3 & 4: 100-Marks Assessment Score Evaluation ---
  const assessment100Html = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[3],
    roadmapForAccordion,
    {
      activeTopicIndex: 2,
      completedTopics: { 'm-c4': [0, 1] },
      chapterAssessmentResult: {
        score: 85,
        max_score: 100,
        percentage: 85,
        passed: true,
        mcqScore: 28,
        maxMcqScore: 30,
        codingScore: 57,
        codingMax: 70
      },
      assessments: []
    }
  );
  assert.match(assessment100Html, /85% Score \(Benchmark Met\)/);
  assert.match(assessment100Html, /Stage 1 \(MCQs\): <strong>28 \/ 30 pts<\/strong>/);
  assert.match(assessment100Html, /Stage 2 \(Coding\): <strong>57 \/ 70 pts<\/strong>/);
  assert.match(assessment100Html, /Total: <strong>85 \/ 100 pts \(85%\)<\/strong>/);

  // --- Prompt 9 Verification: Auto-Complete on Quick Check Pass & Clean Topic Layout ---
  const autoCompletedTopicWorkspace = renderDedicatedLessonWorkspace(
    roadmapForAccordion.milestones[0],
    roadmapForAccordion,
    {
      activeTopicIndex: 0,
      completedTopics: { [roadmapForAccordion.milestones[0].milestone_id]: [0] },
      topicKnowledgeCheckVerified: { [`${roadmapForAccordion.milestones[0].milestone_id}_0`]: true },
      assessments: []
    }
  );
  assert.match(autoCompletedTopicWorkspace, /Topic Completed ✓/);
  assert.match(autoCompletedTopicWorkspace, /lp-btn-success/);
  assert.doesNotMatch(autoCompletedTopicWorkspace, /id="lpContinueTopicBtn"[^>]*disabled/);
  assert.doesNotMatch(autoCompletedTopicWorkspace, /lp-course-tabs-bar/);
  assert.doesNotMatch(autoCompletedTopicWorkspace, /📖 Deep Dive &amp; Guide|📖 Deep Dive & Guide/);

  // --- Prompt 9 Verification: Distinct Video IDs for Individual Topics ---
  const c4TopicsRoadmap = {
    title: 'C Programming',
    milestones: [{
      milestone_id: 'm-c-test',
      title: 'Introduction to C',
      skill_name: 'C Programming',
      learning_objectives: [
        'What is C Programming',
        'Applications of C & System Architecture',
        'Installing & Configuring GCC Compiler',
        'Writing, Compiling & Running Your First C Program'
      ]
    }]
  };
  const getEmbedVid = (html) => (html.match(/youtube-nocookie\.com\/embed\/([a-zA-Z0-9_-]+)/) || [])[1];
  const cVid0 = getEmbedVid(renderDedicatedLessonWorkspace(c4TopicsRoadmap.milestones[0], c4TopicsRoadmap, { activeTopicIndex: 0, assessments: [] }));
  const cVid1 = getEmbedVid(renderDedicatedLessonWorkspace(c4TopicsRoadmap.milestones[0], c4TopicsRoadmap, { activeTopicIndex: 1, assessments: [] }));
  const cVid2 = getEmbedVid(renderDedicatedLessonWorkspace(c4TopicsRoadmap.milestones[0], c4TopicsRoadmap, { activeTopicIndex: 2, assessments: [] }));
  const cVid3 = getEmbedVid(renderDedicatedLessonWorkspace(c4TopicsRoadmap.milestones[0], c4TopicsRoadmap, { activeTopicIndex: 3, assessments: [] }));

  assert.ok(cVid0 && cVid1 && cVid2 && cVid3, 'All 4 topics must resolve a playable YouTube video ID');
  const distinctVids = new Set([cVid0, cVid1, cVid2, cVid3]);
  assert.equal(distinctVids.size, 4, 'Topics 0, 1, 2, and 3 must resolve 4 distinct video IDs');

  // --- Prompt 9 Verification: JavaScript & Python Coding Specs Omit C Pointers ---
  const jsRoadmap = {
    title: 'JavaScript Development',
    milestones: [{ milestone_id: 'm-js-specs', title: 'JS Async & Scope', skill_name: 'JavaScript', learning_objectives: ['Async Patterns'] }]
  };
  const pyRoadmap = {
    title: 'Python Mastery',
    milestones: [{ milestone_id: 'm-py-specs', title: 'Python Data Structures', skill_name: 'Python', learning_objectives: ['Lists & Tuples'] }]
  };
  const jsCodingHtml = renderDedicatedLessonWorkspace(
    jsRoadmap.milestones[0],
    jsRoadmap,
    { activeTopicIndex: 'assessment', completedTopics: { 'm-js-specs': [0] }, chapterAssessmentActive: true, assessmentStage: 'stage2_coding', chapterAssessmentTimer: 3600, assessments: [] }
  );
  const pyCodingHtml = renderDedicatedLessonWorkspace(
    pyRoadmap.milestones[0],
    pyRoadmap,
    { activeTopicIndex: 'assessment', completedTopics: { 'm-py-specs': [0] }, chapterAssessmentActive: true, assessmentStage: 'stage2_coding', chapterAssessmentTimer: 3600, assessments: [] }
  );
  assert.doesNotMatch(jsCodingHtml, /const int \*arr/);
  assert.doesNotMatch(pyCodingHtml, /const int \*arr/);
  assert.match(jsCodingHtml, /numbers: number\[\]/);
  assert.match(pyCodingHtml, /values: list\[int\]/);

  // --- Prompt 9 Verification: Progress Modal Never Rendered & Honest Zero-State ---
  assert.equal(renderDetailedProgressModal(), '', 'Detailed progress modal must return empty string');
  const zeroStateHtml = renderDedicatedProgressSection({ personalizedRoadmap: null });
  assert.match(zeroStateHtml, /0%/);
  assert.match(zeroStateHtml, /No Active Roadmap Tracked Yet/);
  assert.match(zeroStateHtml, /id="lpCreateRoadmapFromProgressBtn"/);

  // --- Prompt 10 Verification: Progressive Cooldown Warning Modal ---
  const penaltyModalHtml = renderProctorPenaltyModal({
    proctorPenaltyActive: true,
    chapterAssessmentStrikes: 2,
    proctorPenaltyRemaining: 20,
    proctorViolationReason: 'Browser window lost focus during examination'
  });
  assert.match(penaltyModalHtml, /Proctoring Warning: Academic Integrity Alert/);
  assert.match(penaltyModalHtml, /Strike 2 of 6/);
  assert.match(penaltyModalHtml, /Wait 20s to resume/);
  assert.match(penaltyModalHtml, /id="lpResumeAfterPenaltyBtn"/);
  assert.match(penaltyModalHtml, /id="lpClosePenaltyModalBtn"/);

  // --- Prompt 10 Verification: Non-Coding Figma Studio Assessment Stage 2 ---
  const uiuxRoadmap = {
    title: 'UI/UX Design',
    milestones: [{
      milestone_id: 'm-uiux-ch1',
      title: 'Design Foundations',
      skill_name: 'UI/UX Design',
      learning_objectives: ['Figma Design System']
    }]
  };
  const figmaStage2Html = renderDedicatedLessonWorkspace(
    uiuxRoadmap.milestones[0],
    uiuxRoadmap,
    {
      activeTopicIndex: 'assessment',
      completedTopics: { 'm-uiux-ch1': [0] },
      chapterAssessmentActive: true,
      assessmentStage: 'stage2_coding',
      chapterAssessmentTimer: 3600,
      assessments: []
    }
  );
  assert.match(figmaStage2Html, /TS-UIUX-CH1-104/);
  assert.match(figmaStage2Html, /id="lpFigmaPdfUploadInput"/);
  assert.match(figmaStage2Html, /id="lpFigmaChallengeConfirmed"/);
  assert.match(figmaStage2Html, /id="lpAssessmentCaseStudyInput"/);
  assert.match(figmaStage2Html, /id="lpFigmaPrototypeUrlInput"/);
  assert.match(figmaStage2Html, /FIGMA STUDIO CHALLENGE/);

  // --- Prompt 10 Verification: Role Roadmap End-of-Roadmap Live Hiring Section ---
  const roleRoadmap = {
    title: 'Frontend Engineer Career Path',
    plan_type: 'role',
    target_role: 'Frontend Engineer',
    summary: 'Master modern web architecture, JavaScript, and interview readiness.',
    milestones: [
      { milestone_id: 'm1', title: 'JavaScript & React', status: 'completed' },
      { milestone_id: 'm2', title: 'Quantitative & Aptitude Prep', status: 'completed' },
      { milestone_id: 'm3', title: 'System Design Mock Simulation', status: 'completed' }
    ]
  };
  const roleRoadmapHtml = renderPersonalizedRoadmap(roleRoadmap, {});
  assert.match(roleRoadmapHtml, /Live Hiring &amp; Job Matches for Frontend Engineer/);
  assert.match(roleRoadmapHtml, /CAREER ACCELERATION/);
  assert.match(roleRoadmapHtml, /View in Market Intelligence/);

  // --- Prompt 10 Verification: Completed Courses History & Wizard Re-Create Block ---
  localStore.clear();
  assert.deepEqual(getCompletedCoursesHistory(), []);
  recordCompletedCourse(roleRoadmap);
  const recordedHistory = getCompletedCoursesHistory();
  assert.equal(recordedHistory.length, 1);
  assert.equal(recordedHistory[0].target, 'frontend engineer');

  const wizardStep2Html = renderRoadmapWizardModal({
    planStep: 2,
    planForm: { plan_type: 'role', target_role: 'Frontend Engineer', starting_level: 'beginner' }
  });
  assert.match(wizardStep2Html, /You have already mastered the/);
  assert.match(wizardStep2Html, /Beginner \(Completed ✓\)/);
  assert.match(wizardStep2Html, /disabled/);
} finally {
  globalThis.fetch = originalFetch;
}

console.log('LEARNING WORKSPACE CLIENT TESTS: resource progress, thumbnail validation, topic completion, navigation and multi-skill curriculum passed');


