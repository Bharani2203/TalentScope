// ============================================================================
// TalentScope.ai — Comprehensive Learning & Roadmap Data Architecture
// Single source of truth for Personal Learning Workspace & Active Roadmaps
// ============================================================================

export const roadmapStorageKey = 'talentscope-learning-roadmap-v1';
export const legacyRoadmapStorageKey = 'talentscope-roadmap-state-v1';

export const ROADMAP_GOAL_TYPES = {
  IMPROVE_SKILL: 'Improve Skill',
  LEARN_SKILL: 'Learn Skill',
  JOB_PREPARATION: 'Job Preparation',
  COMPANY_PREPARATION: 'Company Preparation'
};

// ----------------------------------------------------------------------------
// Canonical Roadmap Presets for Each Goal Type
// ----------------------------------------------------------------------------

export const ROADMAP_PRESETS = {
  'Improve Skill': {
    id: 'rm-python-backend-advancement',
    title: 'Python — Backend Development',
    goalType: 'Improve Skill',
    skill: 'Python',
    targetRole: 'Backend Developer',
    targetCompany: 'Enterprise Tech',
    estimatedRemainingWork: '4 milestones remaining · ~18h estimated',
    achievementStatus: 'On Track · +14% progress this week',
    summary: 'Elevate your core Python expertise toward scalable backend architectures, async pipelines, high-concurrency benchmarks, and production-grade APIs.',
    streakDays: 7,
    learningTimeHours: 12.4,
    milestones: [
      {
        id: 'ms-foundations',
        name: 'Architecture & Foundations',
        label: 'Advanced Architecture Review',
        description: 'Review modular architecture, design patterns, and idiomatic Python 3.12 structures.',
        status: 'completed',
        progress: 100,
        estimatedMinutes: 240,
        topics: [
          { id: 'top-py-adv-syntax', title: 'Generators & Memory Efficiency', status: 'completed', progress: 100, estimatedMinutes: 45 },
          { id: 'top-py-oop-patterns', title: 'Clean Architecture & Dependency Injection', status: 'completed', progress: 100, estimatedMinutes: 60 },
          { id: 'top-py-typing', title: 'Strict Type Hinting & Protocols', status: 'completed', progress: 100, estimatedMinutes: 50 },
          { id: 'top-py-metaclass', title: 'Metaclasses & Dynamic Attributes', status: 'completed', progress: 100, estimatedMinutes: 45 }
        ]
      },
      {
        id: 'ms-async-concurrency',
        name: 'Async & Concurrency Systems',
        label: 'AsyncIO & Parallel Processing',
        description: 'Master non-blocking I/O event loops, thread pools, and distributed task queues.',
        status: 'completed',
        progress: 100,
        estimatedMinutes: 300,
        topics: [
          { id: 'top-py-asyncio-core', title: 'AsyncIO Event Loop Mechanics', status: 'completed', progress: 100, estimatedMinutes: 60 },
          { id: 'top-py-task-queues', title: 'Distributed Workers with Celery & Redis', status: 'completed', progress: 100, estimatedMinutes: 75 },
          { id: 'top-py-concurrency-locks', title: 'Race Conditions, Mutexes & Semaphores', status: 'completed', progress: 100, estimatedMinutes: 55 }
        ]
      },
      {
        id: 'ms-assessment',
        name: 'Proficiency Benchmark Assessment',
        label: 'Technical Proficiency Benchmark',
        description: 'Verify advanced capabilities under simulated timed engineering benchmarks.',
        status: 'current',
        progress: 68,
        estimatedMinutes: 60,
        topics: [
          { id: 'top-py-bench-eval', title: 'High-Concurrency Runtime Benchmark', status: 'in-progress', progress: 68, estimatedMinutes: 35 },
          { id: 'top-py-error-review', title: 'Error & Exception Handling Hardening', status: 'needs-review', progress: 50, estimatedMinutes: 40 }
        ]
      },
      {
        id: 'ms-realworld-project',
        name: 'High-Throughput REST API Project',
        label: 'Production Systems Capstone',
        description: 'Construct a resilient, containerized REST API handling 10k requests/sec.',
        status: 'upcoming',
        progress: 40,
        estimatedMinutes: 480,
        topics: [
          { id: 'top-py-fastapi-arch', title: 'FastAPI Microservice Engine', status: 'in-progress', progress: 40, estimatedMinutes: 120 },
          { id: 'top-py-sql-optim', title: 'SQLAlchemy Async Connection Pooling', status: 'not-started', progress: 0, estimatedMinutes: 90 },
          { id: 'top-py-docker-sandbox', title: 'Containerization & Multi-stage Builds', status: 'not-started', progress: 0, estimatedMinutes: 80 }
        ]
      },
      {
        id: 'ms-role-alignment',
        name: 'Production Hardening & Verification',
        label: 'Production Readiness & Verification',
        description: 'Benchmark telemetry, load testing with Locust, and final architecture review.',
        status: 'upcoming',
        progress: 0,
        estimatedMinutes: 240,
        topics: [
          { id: 'top-py-profiling', title: 'Memory Profiling with cProfile & Memray', status: 'not-started', progress: 0, estimatedMinutes: 75 },
          { id: 'top-py-ci-cd', title: 'Automated CI/CD Quality Gates & Linting', status: 'not-started', progress: 0, estimatedMinutes: 65 }
        ]
      }
    ],
    currentStep: {
      id: 'step-bench-assessment',
      name: 'Assessment: High-Concurrency Benchmark',
      milestoneId: 'ms-assessment',
      topicId: 'top-py-bench-eval',
      detail: 'Technical Benchmark · 12 / 20 modules completed',
      progress: 68,
      estimatedMinutes: 35,
      description: 'Validate concurrency patterns, async exception boundaries, and async task orchestration.',
      prerequisites: 'AsyncIO Event Loop Mechanics completed'
    },
    nextStep: {
      id: 'step-realworld-project',
      name: 'Real-world Project: FastAPI Microservice Engine',
      milestoneId: 'ms-realworld-project',
      topicId: 'top-py-fastapi-arch',
      detail: 'Capstone build · 2 production targets queued',
      estimatedMinutes: 120,
      description: 'Build asynchronous endpoints with Pydantic v2 schemas and connection-pooled Postgres.'
    },
    smartNextAction: {
      title: 'Review Exception Handling & Error Boundaries',
      reason: 'Recent assessment score identified Error Handling (69%) as needing reinforcement before capstone delivery.',
      badgeText: 'NEEDS ATTENTION',
      actionLabel: 'Review Topic Now',
      actionType: 'review-topic',
      targetId: 'top-py-error-review'
    },
    assessments: [
      {
        id: 'asm-py-fundamentals',
        title: 'Python Advanced Technical Benchmark',
        topic: 'Concurrency & Backend Systems',
        difficulty: 'Medium-Hard',
        score: 82,
        passingScore: 70,
        bestScore: 86,
        previousScore: 74,
        attempts: 2,
        timeMinutes: 45,
        status: 'completed',
        trend: [74, 82, 86],
        categories: [
          { name: 'Python Basics & OOP', score: 92, status: 'strong' },
          { name: 'Data Structures & Algorithmic Logic', score: 84, status: 'strong' },
          { name: 'AsyncIO & Concurrency Functions', score: 78, status: 'satisfactory' },
          { name: 'Error Handling & Resilience', score: 69, status: 'needs-review' }
        ],
        weakArea: {
          category: 'Error Handling & Resilience',
          score: 69,
          recommendation: 'Review custom exception hierarchies, context managers, and async exception groups.',
          topicId: 'top-py-error-review',
          resourceId: 'res-py-exception-handling'
        }
      },
      {
        id: 'asm-py-fastapi',
        title: 'FastAPI Production Engineering Bar',
        topic: 'API Design & Optimization',
        difficulty: 'Hard',
        score: 0,
        passingScore: 75,
        bestScore: 0,
        previousScore: 0,
        attempts: 0,
        timeMinutes: 60,
        status: 'recommended',
        trend: [],
        categories: [
          { name: 'Dependency Injection', score: 0, status: 'pending' },
          { name: 'Pydantic v2 Serialization', score: 0, status: 'pending' },
          { name: 'Middleware & Security', score: 0, status: 'pending' }
        ]
      }
    ],
    projects: [
      {
        id: 'proj-fastapi-engine',
        title: 'High-Throughput REST API Engine',
        subtitle: 'Scalable Microservice with Async Postgres & Redis Caching',
        difficulty: 'Advanced',
        progress: 40,
        status: 'in-progress',
        skills: ['Python', 'FastAPI', 'PostgreSQL', 'Redis', 'Docker'],
        timeEstimate: '12 — 15 hours',
        tasks: [
          { id: 'task-1', title: 'Pydantic v2 schemas and request validation pipelines', completed: true },
          { id: 'task-2', title: 'Asynchronous database connection pool with SQLAlchemy 2.0', completed: true },
          { id: 'task-3', title: 'Distributed rate limiting and token bucket with Redis', completed: false },
          { id: 'task-4', title: 'Docker containerization with multi-stage non-root build', completed: false },
          { id: 'task-5', title: 'Load simulation benchmarks with Locust reaching 10k rps', completed: false }
        ],
        readinessContribution: '+22% Backend Architecture Readiness'
      }
    ],
    resources: [
      {
        id: 'res-py-exception-handling',
        title: 'Python Exception Handling & Resilient Fault Boundaries',
        source: 'Python Official Documentation',
        type: 'documentation',
        difficulty: 'Intermediate',
        estimatedMinutes: 20,
        topicId: 'top-py-error-review',
        topicTitle: 'Error & Exception Handling Hardening',
        status: 'in-progress',
        saved: true,
        url: 'https://docs.python.org/3/tutorial/errors.html'
      },
      {
        id: 'res-py-asyncio-deep',
        title: 'AsyncIO in Production: Event Loops and Race Mitigation',
        source: 'Real Python',
        type: 'tutorial',
        difficulty: 'Advanced',
        estimatedMinutes: 35,
        topicId: 'top-py-asyncio-core',
        topicTitle: 'AsyncIO Event Loop Mechanics',
        status: 'completed',
        saved: true,
        url: 'https://realpython.com/async-io-python/'
      },
      {
        id: 'res-py-fastapi-guide',
        title: 'Building Resilient Microservices with FastAPI & Asyncpg',
        source: 'FastAPI Guides',
        type: 'article',
        difficulty: 'Advanced',
        estimatedMinutes: 25,
        topicId: 'top-py-fastapi-arch',
        topicTitle: 'FastAPI Microservice Engine',
        status: 'not-started',
        saved: false,
        url: 'https://fastapi.tiangolo.com/tutorial/'
      },
      {
        id: 'res-py-locust-perf',
        title: 'Locust Load Testing & Telemetry Analysis Lab',
        source: 'Locust.io',
        type: 'practice',
        difficulty: 'Intermediate',
        estimatedMinutes: 40,
        topicId: 'top-py-profiling',
        topicTitle: 'Memory Profiling with cProfile & Memray',
        status: 'not-started',
        saved: false,
        url: 'https://locust.io/'
      },
      {
        id: 'res-py-clean-arch-video',
        title: 'Clean Architecture Patterns in Modern Python Backends',
        source: 'ArjanCodes',
        type: 'video',
        difficulty: 'Advanced',
        estimatedMinutes: 42,
        topicId: 'top-py-oop-patterns',
        topicTitle: 'Clean Architecture & Dependency Injection',
        status: 'completed',
        saved: true,
        url: 'https://youtube.com'
      }
    ],
    practices: [
      {
        id: 'prac-py-async-queue',
        title: 'Asynchronous Semaphore Worker Pool',
        type: 'Coding Practice',
        difficulty: 'Hard',
        estimatedMinutes: 30,
        status: 'completed',
        description: 'Implement a bounded worker queue using asyncio.Queue and asyncio.Semaphore to process 1,000 tasks without memory spikes.'
      },
      {
        id: 'prac-py-error-guard',
        title: 'Custom Exception Hierarchies & Context Manager Guard',
        type: 'Debugging Lab',
        difficulty: 'Medium',
        estimatedMinutes: 25,
        status: 'in-progress',
        description: 'Design a resilient transaction context manager that suppresses non-fatal operational timeouts while preserving audit trails.'
      },
      {
        id: 'prac-py-fastapi-auth',
        title: 'OAuth2 JWT Bearer Pipeline & Scopes',
        type: 'Hands-on Task',
        difficulty: 'Medium-Hard',
        estimatedMinutes: 40,
        status: 'not-started',
        description: 'Wire up cryptographic token verification with role-based access control decorators.'
      }
    ],
    planner: [
      {
        id: 'plan-1',
        title: 'Error & Exception Handling Hardening',
        timeframe: 'Today',
        timeString: 'Today · 3:00 PM',
        durationMinutes: 40,
        status: 'in-progress',
        type: 'Topic Review'
      },
      {
        id: 'plan-2',
        title: 'Retake Error Handling Benchmark Quiz',
        timeframe: 'Today',
        timeString: 'Today · 4:30 PM',
        durationMinutes: 25,
        status: 'pending',
        type: 'Assessment'
      },
      {
        id: 'plan-3',
        title: 'FastAPI Microservice Engine Architecture',
        timeframe: 'This Week',
        timeString: 'Tomorrow · 10:00 AM',
        durationMinutes: 90,
        status: 'pending',
        type: 'Project Work'
      },
      {
        id: 'plan-4',
        title: 'Asyncio Semaphore Worker Pool Lab',
        timeframe: 'This Week',
        timeString: 'Thursday · 2:00 PM',
        durationMinutes: 45,
        status: 'pending',
        type: 'Practice Lab'
      }
    ],
    activityLog: [
      { id: 'act-1', text: 'Completed topic "AsyncIO Event Loop Mechanics"', time: '2 hours ago', icon: 'check-circle-2', type: 'topic' },
      { id: 'act-2', text: 'Achieved 82% on Python Advanced Technical Benchmark', time: 'Yesterday', icon: 'award', type: 'assessment' },
      { id: 'act-3', text: 'Completed practice "Asynchronous Semaphore Worker Pool"', time: '2 days ago', icon: 'terminal', type: 'practice' },
      { id: 'act-4', text: 'Bookmarked "Python Exception Handling & Resilient Fault Boundaries"', time: '3 days ago', icon: 'bookmark', type: 'resource' }
    ],
    aiInsight: {
      headline: 'Strong Concurrency Mastery · Reinforce Exception Boundaries',
      body: 'Your async event loop diagnostics and data structure benchmarks are tracking in the 85th percentile. Exception handling scored 69% on your last attempt. Completing the targeted review topic will raise your overall benchmark above the 80% certification bar.',
      primaryAction: { label: 'Review Exception Handling', targetTopicId: 'top-py-error-review' },
      secondaryAction: { label: 'Take Practice Quiz', targetPracticeId: 'prac-py-error-guard' }
    }
  },

  'Learn Skill': {
    id: 'rm-learn-python-mastery',
    title: 'Python — Zero to Mastery Foundations',
    goalType: 'Learn Skill',
    skill: 'Python',
    targetRole: 'Software Developer',
    targetCompany: 'General Technology',
    estimatedRemainingWork: '5 milestones remaining · ~28h estimated',
    achievementStatus: 'On Track · +18% progress this week',
    summary: 'Build complete fundamental competence in modern Python: syntax, algorithmic structures, object orientation, standard libraries, and testing.',
    streakDays: 4,
    learningTimeHours: 8.5,
    milestones: [
      {
        id: 'ms-py-basics',
        name: 'Fundamentals & Syntax',
        label: 'Core Syntax & Control Flow',
        description: 'Variables, primitive data types, conditionals, loops, and function signatures.',
        status: 'completed',
        progress: 100,
        estimatedMinutes: 200,
        topics: [
          { id: 'top-py-var-types', title: 'Data Types, Operators & Strings', status: 'completed', progress: 100, estimatedMinutes: 40 },
          { id: 'top-py-control-flow', title: 'Conditionals, Loops & Iterators', status: 'completed', progress: 100, estimatedMinutes: 50 },
          { id: 'top-py-func-basics', title: 'Functions, Scopes & Return Values', status: 'completed', progress: 100, estimatedMinutes: 50 }
        ]
      },
      {
        id: 'ms-py-data-struct',
        name: 'Core Data Structures',
        label: 'Lists, Dictionaries, Sets & Tuples',
        description: 'Deep understanding of memory complexity and operations on composite types.',
        status: 'current',
        progress: 55,
        estimatedMinutes: 220,
        topics: [
          { id: 'top-py-lists-dicts', title: 'Dictionary Comprehensions & Hash Maps', status: 'in-progress', progress: 70, estimatedMinutes: 45 },
          { id: 'top-py-sets-tuples', title: 'Immutable Tuples & Set Logic', status: 'not-started', progress: 0, estimatedMinutes: 35 }
        ]
      },
      {
        id: 'ms-py-oop',
        name: 'Object Oriented Programming',
        label: 'Classes, Inheritance & Protocols',
        description: 'Modeling real-world domains with encapsulated classes and inheritance hierarchies.',
        status: 'upcoming',
        progress: 0,
        estimatedMinutes: 260,
        topics: [
          { id: 'top-py-classes', title: 'Class Structures, Dunder Methods & Properties', status: 'not-started', progress: 0, estimatedMinutes: 60 }
        ]
      },
      {
        id: 'ms-py-capstone',
        name: 'Applied Capstone Project',
        label: 'Command Line Application',
        description: 'Construct a multi-module CLI tool with file storage and automated testing.',
        status: 'upcoming',
        progress: 0,
        estimatedMinutes: 360,
        topics: [
          { id: 'top-py-cli-build', title: 'Argparse / Click CLI Architecture', status: 'not-started', progress: 0, estimatedMinutes: 90 }
        ]
      }
    ],
    currentStep: {
      id: 'step-py-dict-comprehensions',
      name: 'Topic: Dictionary Comprehensions & Hash Maps',
      milestoneId: 'ms-py-data-struct',
      topicId: 'top-py-lists-dicts',
      detail: 'Core Data Structures · 5/12 topics completed',
      progress: 70,
      estimatedMinutes: 45,
      description: 'Master fast key lookups, nested dictionary transformations, and hash table collisions.',
      prerequisites: 'Functions, Scopes & Return Values completed'
    },
    nextStep: {
      id: 'step-py-sets-tuples',
      name: 'Topic: Immutable Tuples & Set Logic',
      milestoneId: 'ms-py-data-struct',
      topicId: 'top-py-sets-tuples',
      detail: 'Core Data Structures · Queued',
      estimatedMinutes: 35,
      description: 'Explore set union/intersection math and memory profiles of named tuples.'
    },
    smartNextAction: {
      title: 'Complete Dictionary Comprehensions Lab',
      reason: 'You are 70% through this fundamental topic. Completing it unlocks the data structure diagnostic benchmark.',
      badgeText: 'CURRENT TOPIC',
      actionLabel: 'Resume Topic',
      actionType: 'resume-topic',
      targetId: 'top-py-lists-dicts'
    },
    assessments: [
      {
        id: 'asm-py-syntax-check',
        title: 'Python Syntax & Logic Diagnostic',
        topic: 'Foundations',
        difficulty: 'Easy-Medium',
        score: 88,
        passingScore: 70,
        bestScore: 88,
        previousScore: 80,
        attempts: 2,
        timeMinutes: 30,
        status: 'completed',
        trend: [80, 88],
        categories: [
          { name: 'Variables & Flow Control', score: 95, status: 'strong' },
          { name: 'Functions & Scopes', score: 85, status: 'strong' },
          { name: 'Collections', score: 75, status: 'satisfactory' }
        ]
      }
    ],
    projects: [
      {
        id: 'proj-py-cli-taskmgr',
        title: 'Personal Task & Inventory Engine (CLI)',
        subtitle: 'Terminal application with JSON persistence and unit tests',
        difficulty: 'Intermediate',
        progress: 20,
        status: 'in-progress',
        skills: ['Python', 'JSON Serialization', 'Pytest', 'Click'],
        timeEstimate: '6 — 8 hours',
        tasks: [
          { id: 't1', title: 'Data structures for task items and categories', completed: true },
          { id: 't2', title: 'CLI command tree (add, list, filter, complete)', completed: false },
          { id: 't3', title: 'Unit test suite with 90% pytest coverage', completed: false }
        ],
        readinessContribution: '+18% Core Python Competency'
      }
    ],
    resources: [
      {
        id: 'res-py-dict-docs',
        title: 'Python Dictionaries & Mapping Types',
        source: 'Python Docs',
        type: 'documentation',
        difficulty: 'Beginner',
        estimatedMinutes: 15,
        topicId: 'top-py-lists-dicts',
        topicTitle: 'Dictionary Comprehensions & Hash Maps',
        status: 'in-progress',
        saved: true,
        url: 'https://docs.python.org/3/tutorial/datastructures.html#dictionaries'
      },
      {
        id: 'res-py-data-struct-video',
        title: 'Python Data Structures Visualized & Benchmarked',
        source: 'freeCodeCamp',
        type: 'video',
        difficulty: 'Beginner',
        estimatedMinutes: 45,
        topicId: 'top-py-lists-dicts',
        topicTitle: 'Dictionary Comprehensions & Hash Maps',
        status: 'not-started',
        saved: false,
        url: 'https://youtube.com'
      }
    ],
    practices: [
      {
        id: 'prac-py-dict-freq',
        title: 'Word Frequency Analyzer with Dict Comprehensions',
        type: 'Coding Practice',
        difficulty: 'Easy-Medium',
        estimatedMinutes: 20,
        status: 'not-started',
        description: 'Count word occurrences and sort inverted indexes in under 15 lines of pythonic code.'
      }
    ],
    planner: [
      {
        id: 'plan-l1',
        title: 'Dictionary Comprehensions & Hash Maps',
        timeframe: 'Today',
        timeString: 'Today · 2:00 PM',
        durationMinutes: 45,
        status: 'in-progress',
        type: 'Topic'
      },
      {
        id: 'plan-l2',
        title: 'Word Frequency Coding Lab',
        timeframe: 'Today',
        timeString: 'Today · 3:30 PM',
        durationMinutes: 20,
        status: 'pending',
        type: 'Practice'
      }
    ],
    activityLog: [
      { id: 'act-l1', text: 'Completed topic "Functions, Scopes & Return Values"', time: '4 hours ago', icon: 'check-circle-2', type: 'topic' },
      { id: 'act-l2', text: 'Scored 88% on Python Syntax & Logic Diagnostic', time: 'Yesterday', icon: 'award', type: 'assessment' }
    ],
    aiInsight: {
      headline: 'Excellent Syntax Foundations · Transition to Collections',
      body: 'You completed procedural syntax in record time with 95% evaluation accuracy. As you dive into dictionaries and hash maps, focus on comprehension syntax to write cleaner, more idiomatic solutions.',
      primaryAction: { label: 'Continue Dictionaries Lab', targetTopicId: 'top-py-lists-dicts' },
      secondaryAction: { label: 'Practice Frequency Analyzer', targetPracticeId: 'prac-py-dict-freq' }
    }
  },

  'Job Preparation': {
    id: 'rm-job-ai-engineer-prep',
    title: 'Prepare for AI Engineer Roles',
    goalType: 'Job Preparation',
    skill: 'AI / Machine Learning',
    targetRole: 'AI Engineer',
    targetCompany: 'Top AI Employers (NVIDIA, OpenAI, Google)',
    estimatedRemainingWork: '3 milestones remaining · ~22h estimated',
    achievementStatus: 'High Momentum · +22% requisition match this month',
    summary: 'Directly bridge target role skill gaps in Large Language Model fine-tuning, retrieval-augmented generation (RAG), vector embeddings, and CUDA acceleration.',
    streakDays: 9,
    learningTimeHours: 19.5,
    milestones: [
      {
        id: 'ms-job-gap-align',
        name: 'Role Requirements & Gap Diagnostics',
        label: 'Production Requisition Match',
        description: 'Verify current skill footprint against 2,480 active AI Engineer job postings.',
        status: 'completed',
        progress: 100,
        estimatedMinutes: 180,
        topics: [
          { id: 'top-job-req-matrix', title: 'AI Engineer Production Skill Matrix', status: 'completed', progress: 100, estimatedMinutes: 45 },
          { id: 'top-job-py-ml-eval', title: 'PyTorch Model Evaluation & Metrics', status: 'completed', progress: 100, estimatedMinutes: 60 }
        ]
      },
      {
        id: 'ms-job-rag-vector',
        name: 'Vector Search & Enterprise RAG Systems',
        label: 'Production Systems Deep Dive',
        description: 'Build enterprise hybrid search with embedding rerankers and contextual compression.',
        status: 'current',
        progress: 60,
        estimatedMinutes: 320,
        topics: [
          { id: 'top-job-embeddings', title: 'Vector Embeddings & Cosine Space Geometry', status: 'completed', progress: 100, estimatedMinutes: 60 },
          { id: 'top-job-hybrid-rag', title: 'Hybrid BM25 + Vector Search Pipeline', status: 'in-progress', progress: 60, estimatedMinutes: 80 },
          { id: 'top-job-agentic-tool', title: 'Agentic Tool Calling & Function Execution', status: 'not-started', progress: 0, estimatedMinutes: 75 }
        ]
      },
      {
        id: 'ms-job-domain-proj',
        name: 'Enterprise Production Case Study',
        label: 'Domain Project Build',
        description: 'Construct end-to-end multi-modal agent with LangChain/LlamaIndex and streaming API.',
        status: 'upcoming',
        progress: 25,
        estimatedMinutes: 420,
        topics: [
          { id: 'top-job-proj-spec', title: 'Financial Intelligence Agent Architecture', status: 'in-progress', progress: 25, estimatedMinutes: 120 }
        ]
      },
      {
        id: 'ms-job-interview',
        name: 'Technical Bar-Raiser Simulation',
        label: 'System Design & Bar Interview Prep',
        description: 'Simulate technical rounds: prompt latency optimization, token budgeting, and system design.',
        status: 'upcoming',
        progress: 0,
        estimatedMinutes: 240,
        topics: [
          { id: 'top-job-sysdesign', title: 'LLM Serving Architecture at Scale', status: 'not-started', progress: 0, estimatedMinutes: 90 }
        ]
      }
    ],
    currentStep: {
      id: 'step-job-hybrid-rag',
      name: 'Topic: Hybrid BM25 + Vector Search Pipeline',
      milestoneId: 'ms-job-rag-vector',
      topicId: 'top-job-hybrid-rag',
      detail: 'Vector Search & Enterprise RAG · In progress',
      progress: 60,
      estimatedMinutes: 80,
      description: 'Combine sparse reciprocal rank fusion with dense embedding indices for zero hallucination retrieval.',
      prerequisites: 'Vector Embeddings completed'
    },
    nextStep: {
      id: 'step-job-agentic-tool',
      name: 'Topic: Agentic Tool Calling & Function Execution',
      milestoneId: 'ms-job-rag-vector',
      topicId: 'top-job-agentic-tool',
      detail: 'Next in RAG Systems · Queued',
      estimatedMinutes: 75,
      description: 'Implement structured output parsing and deterministic JSON tool invocations.'
    },
    smartNextAction: {
      title: 'Complete Reciprocal Rank Fusion Implementation',
      reason: 'Enterprise RAG queries at target employers require hybrid search. Completing this pipeline satisfies role requisition requirements.',
      badgeText: 'JOB REQUISITION MATCH',
      actionLabel: 'Continue RAG Pipeline',
      actionType: 'resume-topic',
      targetId: 'top-job-hybrid-rag'
    },
    assessments: [
      {
        id: 'asm-job-rag-benchmark',
        title: 'AI Systems Architecture & RAG Evaluation',
        topic: 'AI Engineer Requisition Benchmark',
        difficulty: 'Hard',
        score: 79,
        passingScore: 75,
        bestScore: 84,
        previousScore: 71,
        attempts: 2,
        timeMinutes: 60,
        status: 'completed',
        trend: [71, 79],
        categories: [
          { name: 'Embedding Geometry & Similarity', score: 91, status: 'strong' },
          { name: 'Prompt Engineering & Latency', score: 86, status: 'strong' },
          { name: 'Reranking & Chunking Strategy', score: 72, status: 'satisfactory' },
          { name: 'CUDA Acceleration & Quantization', score: 64, status: 'needs-review' }
        ],
        weakArea: {
          category: 'CUDA Acceleration & Quantization',
          score: 64,
          recommendation: 'Review 4-bit/8-bit weight quantization (AWQ/GPTQ) and vLLM page-attention memory mechanics.',
          topicId: 'top-job-cuda-prep',
          resourceId: 'res-vllm-cuda-guide'
        }
      }
    ],
    projects: [
      {
        id: 'proj-ai-financial-analyst',
        title: 'Enterprise Document Intelligence & RAG Agent',
        subtitle: 'Multi-modal document parser, hybrid vector search, and streaming answers',
        difficulty: 'Advanced Industry Capstone',
        progress: 35,
        status: 'in-progress',
        skills: ['Python', 'LlamaIndex', 'ChromaDB', 'FastAPI', 'OpenAI API'],
        timeEstimate: '14 — 18 hours',
        tasks: [
          { id: 'tj1', title: 'PDF tokenization and semantic chunking with overlapping margins', completed: true },
          { id: 'tj2', title: 'Dense vector database integration with ChromaDB', completed: true },
          { id: 'tj3', title: 'Cohere Reranker v3 integration with top-k compression', completed: false },
          { id: 'tj4', title: 'Streaming SSE response generator with citation links', completed: false }
        ],
        readinessContribution: '+34% AI Engineer Role Readiness'
      }
    ],
    resources: [
      {
        id: 'res-rag-hybrid-paper',
        title: 'Precise Retrieval with Reciprocal Rank Fusion and Cross-Encoders',
        source: 'ArXiv AI Research',
        type: 'article',
        difficulty: 'Advanced',
        estimatedMinutes: 30,
        topicId: 'top-job-hybrid-rag',
        topicTitle: 'Hybrid BM25 + Vector Search Pipeline',
        status: 'in-progress',
        saved: true,
        url: 'https://arxiv.org'
      },
      {
        id: 'res-vllm-cuda-guide',
        title: 'vLLM and PagedAttention High-Throughput Serving Architecture',
        source: 'vLLM Official Docs',
        type: 'documentation',
        difficulty: 'Advanced',
        estimatedMinutes: 45,
        topicId: 'top-job-cuda-prep',
        topicTitle: 'CUDA Acceleration & Quantization',
        status: 'not-started',
        saved: true,
        url: 'https://docs.vllm.ai/'
      }
    ],
    practices: [
      {
        id: 'prac-job-chunking',
        title: 'Semantic Window Chunking with Token Length Guards',
        type: 'Coding Practice',
        difficulty: 'Medium-Hard',
        estimatedMinutes: 35,
        status: 'completed',
        description: 'Write an intelligent text splitter that breaks documents at semantic boundaries while enforcing maximum context window budgets.'
      }
    ],
    planner: [
      {
        id: 'plan-j1',
        title: 'Hybrid BM25 + Vector Search Pipeline Lab',
        timeframe: 'Today',
        timeString: 'Today · 4:00 PM',
        durationMinutes: 60,
        status: 'in-progress',
        type: 'Topic Lab'
      },
      {
        id: 'plan-j2',
        title: 'Cohere Reranker Module in Capstone Project',
        timeframe: 'This Week',
        timeString: 'Tomorrow · 11:00 AM',
        durationMinutes: 90,
        status: 'pending',
        type: 'Project Work'
      }
    ],
    activityLog: [
      { id: 'act-j1', text: 'Completed topic "Vector Embeddings & Cosine Space Geometry"', time: '3 hours ago', icon: 'check-circle-2', type: 'topic' },
      { id: 'act-j2', text: 'Scored 79% on AI Systems Architecture & RAG Evaluation', time: 'Yesterday', icon: 'award', type: 'assessment' },
      { id: 'act-j3', text: 'Completed practice "Semantic Window Chunking"', time: '2 days ago', icon: 'terminal', type: 'practice' }
    ],
    aiInsight: {
      headline: 'Target Role Alignment: 88% Match for AI Engineer',
      body: 'Your vector database mechanics and embedding pipeline work position you in the upper decile of regional candidates. Quantization and CUDA memory management are the primary gaps identified by hiring requisitions. Prioritize the vLLM serving module to achieve role readiness.',
      primaryAction: { label: 'Continue Hybrid Search', targetTopicId: 'top-job-hybrid-rag' },
      secondaryAction: { label: 'Review CUDA Quantization', targetResourceId: 'res-vllm-cuda-guide' }
    }
  },

  'Company Preparation': {
    id: 'rm-company-nvidia-prep',
    title: 'Prepare for NVIDIA — AI Infrastructure Systems',
    goalType: 'Company Preparation',
    skill: 'CUDA & Accelerated Computing',
    targetRole: 'AI Infrastructure Engineer',
    targetCompany: 'NVIDIA',
    estimatedRemainingWork: '3 milestones remaining · ~24h estimated',
    achievementStatus: 'Target Requisition Active · 1,820 open positions at NVIDIA',
    summary: 'Targeted preparation for NVIDIA engineering standards: TensorRT deployment, Triton Inference Server, CUDA kernel tuning, and multi-GPU interconnect optimization.',
    streakDays: 11,
    learningTimeHours: 23.0,
    milestones: [
      {
        id: 'ms-nv-stack',
        name: 'NVIDIA Enterprise Architecture Review',
        label: 'Target Enterprise Architecture Review',
        description: 'Analyze NVIDIA NeMo, TensorRT-LLM, and Triton inference cluster topologies.',
        status: 'completed',
        progress: 100,
        estimatedMinutes: 240,
        topics: [
          { id: 'top-nv-triton', title: 'Triton Inference Server Architecture', status: 'completed', progress: 100, estimatedMinutes: 60 },
          { id: 'top-nv-tensorrt', title: 'TensorRT-LLM Optimization Pipeline', status: 'completed', progress: 100, estimatedMinutes: 75 }
        ]
      },
      {
        id: 'ms-nv-cuda-kernels',
        name: 'CUDA Kernel Tuning & Memory Hierarchy',
        label: 'Company Tooling & Standards',
        description: 'Warp divergence, shared memory banks, and memory coalescing on Hopper/Blackwell architectures.',
        status: 'current',
        progress: 50,
        estimatedMinutes: 360,
        topics: [
          { id: 'top-nv-shared-mem', title: 'Shared Memory Bank Conflicts & Coalescing', status: 'in-progress', progress: 50, estimatedMinutes: 90 },
          { id: 'top-nv-nccl', title: 'NCCL Distributed All-Reduce Communication', status: 'not-started', progress: 0, estimatedMinutes: 80 }
        ]
      },
      {
        id: 'ms-nv-challenge',
        name: 'NVIDIA Technical Bar Challenge',
        label: 'Company Challenge Assessment',
        description: 'Simulated NVIDIA engineering screening: GPU profiling with Nsight Compute and memory bottlenecks.',
        status: 'upcoming',
        progress: 0,
        estimatedMinutes: 90,
        topics: [
          { id: 'top-nv-nsight-eval', title: 'Nsight Compute Kernel Profiling Simulation', status: 'not-started', progress: 0, estimatedMinutes: 90 }
        ]
      },
      {
        id: 'ms-nv-mock-proj',
        name: 'Production Scale Mock Build',
        label: 'Production Scale Mock Build',
        description: 'Deploy a high-availability model inference cluster with Triton, Prometheus, and dynamic batching.',
        status: 'upcoming',
        progress: 0,
        estimatedMinutes: 480,
        topics: [
          { id: 'top-nv-cluster-deploy', title: 'Multi-GPU Triton Cluster Deployment', status: 'not-started', progress: 0, estimatedMinutes: 120 }
        ]
      }
    ],
    currentStep: {
      id: 'step-nv-shared-mem',
      name: 'Topic: Shared Memory Bank Conflicts & Coalescing',
      milestoneId: 'ms-nv-cuda-kernels',
      topicId: 'top-nv-shared-mem',
      detail: 'CUDA Kernel Tuning · In progress',
      progress: 50,
      estimatedMinutes: 90,
      description: 'Profile 32-bank stride patterns, eliminate serialization stalls, and align 128-byte global memory transactions.',
      prerequisites: 'TensorRT-LLM Optimization completed'
    },
    nextStep: {
      id: 'step-nv-nccl',
      name: 'Topic: NCCL Distributed All-Reduce Communication',
      milestoneId: 'ms-nv-cuda-kernels',
      topicId: 'top-nv-nccl',
      detail: 'Multi-GPU Scalability · Queued',
      estimatedMinutes: 80,
      description: 'Analyze ring-allreduce topology across NVLink switches and RoCE v2 networks.'
    },
    smartNextAction: {
      title: 'Analyze Memory Bank Conflict Telemetry in Nsight',
      reason: 'NVIDIA infrastructure roles rigorously screen for hardware memory alignment. Mastering bank conflict mitigation directly prepares you for the technical bar.',
      badgeText: 'COMPANY TARGET: NVIDIA',
      actionLabel: 'Continue Memory Tuning Lab',
      actionType: 'resume-topic',
      targetId: 'top-nv-shared-mem'
    },
    assessments: [
      {
        id: 'asm-nv-hardware-bar',
        title: 'NVIDIA Systems Engineering Challenge',
        topic: 'CUDA Architecture & Systems Screening',
        difficulty: 'Expert',
        score: 76,
        passingScore: 75,
        bestScore: 82,
        previousScore: 68,
        attempts: 2,
        timeMinutes: 75,
        status: 'completed',
        trend: [68, 76],
        categories: [
          { name: 'Triton Server & Dynamic Batching', score: 90, status: 'strong' },
          { name: 'TensorRT Model Graph Compilation', score: 84, status: 'strong' },
          { name: 'CUDA Kernel Memory Coalescing', score: 68, status: 'needs-review' },
          { name: 'NVLink Interconnect Topologies', score: 72, status: 'satisfactory' }
        ],
        weakArea: {
          category: 'CUDA Kernel Memory Coalescing',
          score: 68,
          recommendation: 'Review stride offsets and warp-level primitives to eliminate warp replay penalties.',
          topicId: 'top-nv-shared-mem',
          resourceId: 'res-nv-cuda-prog-guide'
        }
      }
    ],
    projects: [
      {
        id: 'proj-nv-triton-cluster',
        title: 'High-Availability Triton Inference Cluster',
        subtitle: 'Dynamic batching, FP8 quantization, and Prometheus latency telemetry',
        difficulty: 'Enterprise Scale',
        progress: 30,
        status: 'in-progress',
        skills: ['C++', 'CUDA', 'Python', 'Triton Inference Server', 'Docker', 'Prometheus'],
        timeEstimate: '18 — 24 hours',
        tasks: [
          { id: 'tn1', title: 'Triton model repository configuration with ensemble pipeline', completed: true },
          { id: 'tn2', title: 'Dynamic batch scheduler tuning for sub-20ms SLA latency', completed: false },
          { id: 'tn3', title: 'CUDA stream priority assignment and concurrent kernel launches', completed: false },
          { id: 'tn4', title: 'Prometheus metrics exporter for GPU compute saturation', completed: false }
        ],
        readinessContribution: '+40% NVIDIA AI Systems Readiness'
      }
    ],
    resources: [
      {
        id: 'res-nv-cuda-prog-guide',
        title: 'NVIDIA CUDA C++ Programming Guide: Memory Hierarchy',
        source: 'NVIDIA Developer Zone',
        type: 'documentation',
        difficulty: 'Expert',
        estimatedMinutes: 50,
        topicId: 'top-nv-shared-mem',
        topicTitle: 'Shared Memory Bank Conflicts & Coalescing',
        status: 'in-progress',
        saved: true,
        url: 'https://docs.nvidia.com/cuda/'
      },
      {
        id: 'res-nv-triton-arch',
        title: 'Triton Architecture Deep Dive: Paged Cache & Ensembles',
        source: 'NVIDIA GTC Technical Sessions',
        type: 'video',
        difficulty: 'Advanced',
        estimatedMinutes: 55,
        topicId: 'top-nv-triton',
        topicTitle: 'Triton Inference Server Architecture',
        status: 'completed',
        saved: true,
        url: 'https://developer.nvidia.com'
      }
    ],
    practices: [
      {
        id: 'prac-nv-shared-stride',
        title: 'Warp Transpose Kernel with Padding Elimination',
        type: 'Coding Practice',
        difficulty: 'Expert',
        estimatedMinutes: 45,
        status: 'in-progress',
        description: 'Pad 32x32 shared memory tiles to [32][33] floats to eliminate 32-way bank conflict stalls during matrix transposition.'
      }
    ],
    planner: [
      {
        id: 'plan-n1',
        title: 'Shared Memory Bank Conflicts & Coalescing',
        timeframe: 'Today',
        timeString: 'Today · 5:00 PM',
        durationMinutes: 90,
        status: 'in-progress',
        type: 'CUDA Lab'
      },
      {
        id: 'plan-n2',
        title: 'Dynamic Batch Scheduler Tuning Lab',
        timeframe: 'This Week',
        timeString: 'Wednesday · 10:00 AM',
        durationMinutes: 75,
        status: 'pending',
        type: 'Project Work'
      }
    ],
    activityLog: [
      { id: 'act-n1', text: 'Completed topic "TensorRT-LLM Optimization Pipeline"', time: '1 hour ago', icon: 'check-circle-2', type: 'topic' },
      { id: 'act-n2', text: 'Completed GTC Session "Triton Architecture Deep Dive"', time: 'Yesterday', icon: 'play-circle', type: 'resource' },
      { id: 'act-n3', text: 'Achieved 76% on NVIDIA Systems Engineering Challenge', time: '3 days ago', icon: 'award', type: 'assessment' }
    ],
    aiInsight: {
      headline: 'Target Company: NVIDIA — Technical Alignment at 84%',
      body: 'Your mastery of TensorRT and Triton inference topologies satisfies key requisition criteria for AI Infrastructure requisitions. Memory bank conflict profiling in Nsight remains the highest leverage gap before the technical screening phase.',
      primaryAction: { label: 'Continue Shared Memory Lab', targetTopicId: 'top-nv-shared-mem' },
      secondaryAction: { label: 'Review Memory Documentation', targetResourceId: 'res-nv-cuda-prog-guide' }
    }
  }
};

// Aliases for compatibility
ROADMAP_PRESETS['Career Preparation'] = ROADMAP_PRESETS['Job Preparation'];
ROADMAP_PRESETS['Skill Switch'] = ROADMAP_PRESETS['Improve Skill'];

// ----------------------------------------------------------------------------
// Legacy Stages Generator (ensures compatibility with existing imports)
// ----------------------------------------------------------------------------

export function createRoadmapStages() {
  return [
    { title: 'Core Foundations', desc: 'Master fundamentals and essential paradigms', milestones: ['Setup environment and foundational syntax', 'Complete core algorithmic concepts', 'Build baseline console application'] },
    { title: 'Advanced Concepts', desc: 'Deep-dive into architecture, patterns, and performance', milestones: ['Master asynchronous pipelines and data structures', 'Implement production error handling', 'Optimize runtime performance benchmarks'] },
    { title: 'Practical Integration', desc: 'Apply knowledge to end-to-end production systems', milestones: ['Integrate rest/graphql API endpoints', 'Build automated unit and integration tests', 'Deploy containerized service to cloud sandbox'] }
  ];
}

// ----------------------------------------------------------------------------
// Dynamic Progress Calculation (Step 42)
// Progress is based on roadmap completion criteria, adapting to goal type
// ----------------------------------------------------------------------------

export function calculateRoadmapProgress(roadmap) {
  if (!roadmap) return 0;
  if (roadmap.status === 'completed') return 100;
  if (roadmap.status === 'none' || roadmap.status === 'empty') return 0;

  const milestones = roadmap.milestones || [];
  if (!milestones.length) return roadmap.progress || 0;

  let totalTopics = 0;
  let completedTopics = 0;
  let topicScore = 0;

  milestones.forEach(m => {
    (m.topics || []).forEach(t => {
      totalTopics++;
      if (t.status === 'completed' || t.progress === 100) {
        completedTopics++;
        topicScore += 1;
      } else if (t.status === 'in-progress') {
        topicScore += (t.progress || 50) / 100;
      }
    });
  });

  const topicPct = totalTopics > 0 ? (topicScore / totalTopics) * 100 : 50;

  // Assessments weighting
  const assessments = roadmap.assessments || [];
  let assessmentPct = 70;
  if (assessments.length > 0) {
    const totalScore = assessments.reduce((sum, a) => sum + (a.score || 0), 0);
    assessmentPct = totalScore / assessments.length;
  }

  // Projects weighting
  const projects = roadmap.projects || [];
  let projectPct = 40;
  if (projects.length > 0) {
    const totalProj = projects.reduce((sum, p) => sum + (p.progress || 0), 0);
    projectPct = totalProj / projects.length;
  }

  // Practices weighting
  const practices = roadmap.practices || [];
  let practicePct = 50;
  if (practices.length > 0) {
    const compPrac = practices.filter(p => p.status === 'completed').length;
    practicePct = (compPrac / practices.length) * 100;
  }

  // Adaptive weighting based on goal type (Step 42)
  let calculated = 0;
  const goal = roadmap.goalType || 'Improve Skill';

  if (goal === 'Learn Skill') {
    // Learning: topics 55%, assessment 25%, practice 20%
    calculated = (topicPct * 0.55) + (assessmentPct * 0.25) + (practicePct * 0.20);
  } else if (goal === 'Job Preparation' || goal === 'Career Preparation') {
    // Job prep: topics 30%, assessment 25%, projects 30%, practice 15%
    calculated = (topicPct * 0.30) + (assessmentPct * 0.25) + (projectPct * 0.30) + (practicePct * 0.15);
  } else if (goal === 'Company Preparation') {
    // Company: required skills 35%, assessment 25%, project 25%, practice 15%
    calculated = (topicPct * 0.35) + (assessmentPct * 0.25) + (projectPct * 0.25) + (practicePct * 0.15);
  } else {
    // Improve Skill (default): topics 40%, assessment 20%, project 25%, practice 15%
    calculated = (topicPct * 0.40) + (assessmentPct * 0.20) + (projectPct * 0.25) + (practicePct * 0.15);
  }

  const finalProgress = Math.min(99, Math.max(1, Math.round(calculated)));
  return finalProgress;
}

// ----------------------------------------------------------------------------
// State Persistence and Single-Source-of-Truth
// Synchronizes both 'talentscope-learning-roadmap-v1' and 'talentscope-roadmap-state-v1'
// ----------------------------------------------------------------------------

export function loadLearningRoadmapState() {
  try {
    if (typeof localStorage === 'undefined') {
      return {
        status: 'none',
        progress: 0,
        title: 'No Active Roadmap',
        currentStep: { name: 'Choose a learning path' },
        milestones: []
      };
    }
    const saved = localStorage.getItem(roadmapStorageKey) || localStorage.getItem(legacyRoadmapStorageKey);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed && typeof parsed === 'object') {
        // If it's a complete preset or has milestones, return it
        if (parsed.milestones && parsed.milestones.length > 0) {
          return parsed;
        }
        // If it's a legacy minimal state e.g. { status: 'active', goalType: 'Improve Skill', skill: 'Python' }
        const goal = parsed.goalType || parsed.goal || 'Improve Skill';
        const preset = ROADMAP_PRESETS[goal] || ROADMAP_PRESETS['Improve Skill'];
        const merged = {
          ...JSON.parse(JSON.stringify(preset)),
          ...parsed,
          milestones: parsed.milestones || JSON.parse(JSON.stringify(preset.milestones)),
          status: parsed.status || 'active'
        };
        return merged;
      }
    }
  } catch (err) {
    console.warn('Error reading saved roadmap state:', err);
  }

  // Default initial roadmap state: honest empty state (no synthetic active progress)
  return {
    status: 'none',
    progress: 0,
    title: 'No Active Roadmap',
    currentStep: { name: 'Choose a learning path' },
    milestones: []
  };
}

export function saveLearningRoadmapState(roadmap) {
  try {
    const json = JSON.stringify(roadmap);
    localStorage.setItem(roadmapStorageKey, json);
    localStorage.setItem(legacyRoadmapStorageKey, json);
  } catch (err) {
    console.warn('Failed to save learning roadmap state to localStorage:', err);
  }
}

// Export active roadmapState reference for legacy consumers
export let roadmapState = loadLearningRoadmapState();

export function persistRoadmapState() {
  saveLearningRoadmapState(roadmapState);
}

export function loadRoadmapState() {
  roadmapState = loadLearningRoadmapState();
  return roadmapState;
}
