/**
 * TalentScope.ai — Comprehensive 30-MCQ Assessment Bank
 * Provides 30 rigorous, curriculum-aligned questions per domain track with
 * distributed correct options across A, B, C, and D (~25% each).
 */

const OPTION_IDS = ['opt-a', 'opt-b', 'opt-c', 'opt-d'];

function createQuestion(trackKey, idx, questionText, optTexts, correctIdx) {
  const correctOptId = OPTION_IDS[correctIdx % 4];
  return {
    id: `${trackKey}-q${idx + 1}`,
    question: questionText,
    options: [
      { id: 'opt-a', text: optTexts[0] },
      { id: 'opt-b', text: optTexts[1] },
      { id: 'opt-c', text: optTexts[2] },
      { id: 'opt-d', text: optTexts[3] }
    ],
    correct: correctOptId
  };
}

// ----------------------------------------------------------------------------
// 1. C PROGRAMMING (30 MCQs)
// ----------------------------------------------------------------------------
export const C_MCQ_BANK = [
  createQuestion('c', 0, 'What is stored in a pointer variable in C?', [
    'The memory address of another variable or allocated block',
    'The binary IEEE-754 representation of a float',
    'A hardware register identifier',
    'A copy of the value on the process call stack'
  ], 0), // A

  createQuestion('c', 1, 'What does the unary `*` operator do when applied to an existing pointer expression?', [
    'Allocates memory on the heap equal to sizeof(int)',
    'Dereferences the address to access or mutate the value at that location',
    'Multiplies the address offset by 4 bytes',
    'Returns the pointer address as an unsigned hexadecimal long'
  ], 1), // B

  createQuestion('c', 2, 'Which standard C library function allocates memory and initializes all bytes to zero?', [
    'malloc()',
    'realloc()',
    'calloc()',
    'valloc()'
  ], 2), // C

  createQuestion('c', 3, 'What happens if dynamically allocated heap memory loses all references without calling `free()`?', [
    'The OS invokes the kernel garbage collector automatically',
    'The compiler produces a static linking warning',
    'A segmentation fault is raised immediately',
    'A memory leak occurs, consuming heap memory until process termination'
  ], 3), // D

  createQuestion('c', 4, 'When an array name is passed to a function in C, what does the parameter receive?', [
    'A pointer decaying to the address of the first array element',
    'A complete deep copy of every byte in the array',
    'A struct containing length metadata and bounds info',
    'A read-only immutable slice pointer'
  ], 0), // A

  createQuestion('c', 5, 'What is the evaluation result of `sizeof(char)` according to the ANSI C standard?', [
    'Architecture dependent (1 or 2 bytes)',
    'Always guaranteed to be exactly 1',
    '4 bytes on modern 64-bit architectures',
    '0 unless explicitly initialized'
  ], 1), // B

  createQuestion('c', 6, 'What does the `static` keyword indicate when applied to a global variable in C?', [
    'The variable cannot be mutated after initialization',
    'The variable is stored exclusively in CPU registers',
    'Internal linkage: the variable is scoped strictly to the current translation unit',
    'The variable is allocated on the dynamic heap pool'
  ], 2), // C

  createQuestion('c', 7, 'Which standard header file declares `malloc()`, `calloc()`, `realloc()`, and `free()`?', [
    '<stdio.h>',
    '<string.h>',
    '<memory.h>',
    '<stdlib.h>'
  ], 3), // D

  createQuestion('c', 8, 'What is the purpose of header guards (`#ifndef HEADER_H ... #endif`) in C?', [
    'To prevent duplicate declarations caused by multiple inclusions of the same header',
    'To encrypt header source files from unauthorized inspection',
    'To speed up CPU clock speed during program execution',
    'To automatically declare extern linkage for all functions'
  ], 0), // A

  createQuestion('c', 9, 'What is the effect of the `volatile` qualifier on a variable declaration?', [
    'The variable cannot be modified by any thread or interrupt',
    'Tells the compiler not to optimize away reads/writes because the value may change externally',
    'Forces the variable to be allocated in thread-local storage',
    'Prevents the variable from being passed as a function argument'
  ], 1), // B

  createQuestion('c', 10, 'In C, what is the null terminator character for standard strings?', [
    'ASCII 32 (space)',
    'The string literal "NULL"',
    'The byte \'\\0\' with numerical value 0',
    'EOF (-1)'
  ], 2), // C

  createQuestion('c', 11, 'Which function computes the number of characters in a string excluding the null terminator?', [
    'sizeof()',
    'strcap()',
    'strcount()',
    'strlen()'
  ], 3), // D

  createQuestion('c', 12, 'What is the consequence of accessing an array index beyond its allocated boundary in C?', [
    'Undefined behavior: may read garbage, corrupt memory, or cause a segmentation fault',
    'The runtime throws an ArrayIndexOutOfBoundsException',
    'The array automatically expands its allocation capacity',
    'The compiler automatically wraps the index using modulo arithmetic'
  ], 0), // A

  createQuestion('c', 13, 'What is a memory difference between a `struct` and a `union` in C?', [
    'A struct can only contain primitive data types; a union can contain pointers',
    'A struct allocates space for all members; a union shares the same memory for all members',
    'A union is allocated on the heap; a struct is allocated on the stack',
    'A struct cannot be nested inside another struct; a union can'
  ], 1), // B

  createQuestion('c', 14, 'What does the function signature `int (*fp)(int, int);` declare?', [
    'A function returning a pointer to an integer',
    'An array of two integer pointers',
    'A pointer to a function taking two ints and returning an int',
    'A macro defining an integer comparison callback'
  ], 2), // C

  createQuestion('c', 15, 'What does the bitwise expression `x & (x - 1)` evaluate to for a positive integer `x`?', [
    'Reverses the bit order of x',
    'Multiplies x by two',
    'Checks if x is an odd number',
    'Clears the lowest set bit of x'
  ], 3), // D

  createQuestion('c', 16, 'What is a dangling pointer in C programming?', [
    'A pointer referencing a memory location that has already been freed or deallocated',
    'A pointer that has been explicitly initialized to NULL',
    'A pointer pointing to a read-only code segment',
    'A pointer declared without an explicit type specifier'
  ], 0), // A

  createQuestion('c', 17, 'Which file open mode in `fopen()` appends data to the end of an existing file without truncating?', [
    '"w"',
    '"a"',
    '"r+"',
    '"w+"'
  ], 1), // B

  createQuestion('c', 18, 'What is the difference between `++i` (pre-increment) and `i++` (post-increment)?', [
    'Pre-increment operates on heap pointers; post-increment operates on stack variables',
    'Post-increment is executed by the preprocessor before compilation',
    'Pre-increment increments before evaluating expression value; post-increment evaluates first',
    'There is no difference in semantics or timing'
  ], 2), // C

  createQuestion('c', 19, 'What is the return value of `strcmp("apple", "banana")` in standard C?', [
    '0',
    'Positive integer',
    'Undefined',
    'Negative integer'
  ], 3), // D

  createQuestion('c', 20, 'Why is the `gets()` function deprecated and removed from modern C standards?', [
    'It does not perform buffer bounds checking, leading to buffer overflow vulnerabilities',
    'It only supports ASCII characters up to 7 bits',
    'It requires an active network socket connection',
    'It cannot read newline characters from standard input'
  ], 0), // A

  createQuestion('c', 21, 'What is the purpose of `typedef` in C?', [
    'To declare variables with dynamic types at runtime',
    'To create meaningful alias names for existing data types',
    'To import external library modules',
    'To prevent variables from being reassigned'
  ], 1), // B

  createQuestion('c', 22, 'What does the expression `(void *)0` represent in standard C?', [
    'An invalid memory page fault signal',
    'A pointer to the beginning of the program text segment',
    'The null pointer constant (NULL)',
    'A void function return code'
  ], 2), // C

  createQuestion('c', 23, 'Which storage class specifier requests that a variable be stored in a CPU register for faster access?', [
    'auto',
    'extern',
    'static',
    'register'
  ], 3), // D

  createQuestion('c', 24, 'What is recursion in computer programming?', [
    'A function calling itself directly or indirectly to solve smaller subproblems',
    'A loop construct that repeats an infinite number of iterations',
    'A compilation technique that inlines external library calls',
    'A memory allocation strategy based on buddy blocks'
  ], 0), // A

  createQuestion('c', 25, 'In C pointer arithmetic, if `int *p` points to address 0x1000, what is `p + 1` assuming 4-byte ints?', [
    '0x1001',
    '0x1004',
    '0x1008',
    '0x1002'
  ], 1), // B

  createQuestion('c', 26, 'What is memory alignment in modern computer architectures?', [
    'Placing memory addresses strictly in reverse chronological order',
    'Dividing physical RAM equally among all active user threads',
    'Aligning data in memory at addresses that are multiples of the data size for efficient hardware access',
    'Encrypting memory pages before writing to disk swap space'
  ], 2), // C

  createQuestion('c', 27, 'Which preprocessor directive is used to include function prototypes from system header files?', [
    '#define',
    '#pragma',
    '#extern',
    '#include'
  ], 3), // D

  createQuestion('c', 28, 'What is the purpose of the `const` keyword when applied to a pointer parameter `const int *p`?', [
    'The pointer cannot be used to modify the value of the integer it points to',
    'The pointer variable itself cannot be reassigned to point elsewhere',
    'The integer is allocated in GPU read-only memory',
    'The pointer automatically dereferences to zero'
  ], 0), // A

  createQuestion('c', 29, 'What is the standard prototype for the `main()` function in C when accepting command-line arguments?', [
    'void main(void)',
    'int main(int argc, char *argv[])',
    'int main(string args[])',
    'char *main(int count)'
  ], 1)  // B
];

// ----------------------------------------------------------------------------
// 2. PYTHON (30 MCQs)
// ----------------------------------------------------------------------------
export const PYTHON_MCQ_BANK = [
  createQuestion('py', 0, 'In Python, which dunder method initializes a class instance upon creation?', [
    '__init__',
    '__new__',
    '__setup__',
    '__construct__'
  ], 0), // A

  createQuestion('py', 1, 'What is the average time complexity for key lookup in a Python dictionary?', [
    'O(n)',
    'O(1)',
    'O(log n)',
    'O(n log n)'
  ], 1), // B

  createQuestion('py', 2, 'What does the expression `bool([])` evaluate to in Python?', [
    'True',
    'None',
    'False',
    'TypeError'
  ], 2), // C

  createQuestion('py', 3, 'Which statement correctly pauses execution until an asynchronous coroutine completes?', [
    'yield coroutine_fn()',
    'async coroutine_fn()',
    'defer coroutine_fn()',
    'await coroutine_fn()'
  ], 3), // D

  createQuestion('py', 4, 'How does CPython automatically reclaim memory for objects with circular references?', [
    'A cyclic garbage collector that periodically inspects generation pools',
    'Immediate reference count decrement to zero',
    'Automatic thread stack clearing upon return',
    'Operating system virtual page eviction'
  ], 0), // A

  createQuestion('py', 5, 'What is the difference between a list and a tuple in Python?', [
    'Tuples can store heterogenous objects; lists can only store numbers',
    'Lists are mutable; tuples are immutable',
    'Tuples do not support zero-indexed slicing',
    'Lists cannot be nested inside dictionaries'
  ], 1), // B

  createQuestion('py', 6, 'What is the purpose of the Global Interpreter Lock (GIL) in CPython?', [
    'To encrypt Python bytecode before running on the CPU',
    'To prevent memory access violations across different user accounts',
    'To ensure thread-safety in memory management by allowing only one native thread to execute Python bytecode at a time',
    'To limit recursion depth to 1000 calls'
  ], 2), // C

  createQuestion('py', 7, 'Which keyword turns a standard function into a generator function in Python?', [
    'return',
    'generate',
    'produce',
    'yield'
  ], 3), // D

  createQuestion('py', 8, 'What is the difference between the `is` operator and the `==` operator in Python?', [
    '`is` checks identity (same memory address); `==` checks value equality',
    '`==` checks identity; `is` checks value equality',
    '`is` is only valid for strings; `==` is valid for numbers',
    '`is` raises an exception if operands have different types'
  ], 0), // A

  createQuestion('py', 9, 'What does the `@property` decorator allow a developer to do in Python classes?', [
    'Enforce static type checks at runtime',
    'Access a method like an attribute without calling parentheses',
    'Make an instance method execute on a background worker thread',
    'Persist an attribute directly to SQLite storage'
  ], 1), // B

  createQuestion('py', 10, 'Which module in the Python standard library provides deep and shallow copy operations?', [
    'clone',
    'duplicate',
    'copy',
    'sys'
  ], 2), // C

  createQuestion('py', 11, 'What is the purpose of `*args` and `**kwargs` in a Python function definition?', [
    'To specify pointer dereferencing and memory address parameters',
    'To declare generator return types',
    'To enforce static typing for arguments',
    'To accept arbitrary numbers of positional and keyword arguments'
  ], 3), // D

  createQuestion('py', 12, 'Which dunder methods must be implemented to create a custom context manager for the `with` statement?', [
    '__enter__ and __exit__',
    '__start__ and __stop__',
    '__open__ and __close__',
    '__init__ and __del__'
  ], 0), // A

  createQuestion('py', 13, 'What does the list slicing expression `arr[::-1]` return?', [
    'Every second element of arr',
    'A reversed copy of the list arr',
    'The last element of arr as a singleton list',
    'A ValueError exception'
  ], 1), // B

  createQuestion('py', 14, 'What is Method Resolution Order (MRO) in Python object-oriented programming?', [
    'The order in which methods are compiled into bytecode',
    'The execution priority of asynchronous tasks',
    'The deterministic sequence in which Python searches class hierarchies for an attribute or method (C3 linearization)',
    'The order of argument parsing in decorated functions'
  ], 2), // C

  createQuestion('py', 15, 'What is a lambda function in Python?', [
    'A function that can only run inside asynchronous event loops',
    'A compiled C extension module function',
    'A generator that produces infinite streams',
    'A small, anonymous, single-expression function'
  ], 3), // D

  createQuestion('py', 16, 'What happens in a `try...except...else...finally` block if no exception is raised?', [
    'The code in the `else` block executes, followed by the `finally` block',
    'The `except` block executes with None argument',
    'The `finally` block is skipped entirely',
    'Execution terminates immediately'
  ], 0), // A

  createQuestion('py', 17, 'Which collection type stores unique elements and supports set operations (union, intersection)?', [
    'list',
    'set',
    'tuple',
    'deque'
  ], 1), // B

  createQuestion('py', 18, 'What is the return type of a list comprehension like `[x**2 for x in range(5)]`?', [
    'Generator object',
    'Tuple',
    'List',
    'Iterator'
  ], 2), // C

  createQuestion('py', 19, 'What is the difference between `@classmethod` and `@staticmethod` in Python?', [
    '`@classmethod` can only be called from instances; `@staticmethod` cannot',
    '`@staticmethod` receives `self`; `@classmethod` receives nothing',
    '`@classmethod` is executed during import; `@staticmethod` is executed during call',
    '`@classmethod` receives the class object (`cls`) as its first parameter; `@staticmethod` receives no implicit first parameter'
  ], 3), // D

  createQuestion('py', 20, 'What does the `zip()` built-in function do in Python?', [
    'Aggregates elements from multiple iterables into tuples element-by-element',
    'Compresses files using the ZIP archive format',
    'Combines two dictionaries into a single database table',
    'Sorts an array in ascending order'
  ], 0), // A

  createQuestion('py', 21, 'Which container in `collections` provides constant-time appends and pops from both ends?', [
    'defaultdict',
    'deque',
    'OrderedDict',
    'Counter'
  ], 1), // B

  createQuestion('py', 22, 'What is the output of `type(None)` in Python 3?', [
    '<class \'null\'>',
    '<class \'void\'>',
    '<class \'NoneType\'>',
    '<class \'object\'>'
  ], 2), // C

  createQuestion('py', 23, 'How can you unpack dictionary key-value pairs into another dictionary in Python 3.9+?', [
    'dict.merge(d1, d2)',
    'd1 + d2',
    'd1 & d2',
    'd1 | d2 or {**d1, **d2}'
  ], 3), // D

  createQuestion('py', 24, 'What is the purpose of the `__repr__` method compared to `__str__` in Python?', [
    '`__repr__` aims to provide an unambiguous, developer-focused representation; `__str__` provides a human-readable string',
    '`__repr__` formats numbers into scientific notation; `__str__` formats text',
    '`__repr__` is used only for logging errors; `__str__` is used for print()',
    '`__str__` returns bytes; `__repr__` returns unicode'
  ], 0), // A

  createQuestion('py', 25, 'What does the `collections.Counter` class do?', [
    'Counts the CPU cycles spent executing a function',
    'A dictionary subclass for counting hashable objects (frequency table)',
    'An infinite number generator starting at 0',
    'A thread synchronization semaphore'
  ], 1), // B

  createQuestion('py', 26, 'Which keyword is used to access and modify a variable in the enclosing (outer non-global) scope?', [
    'global',
    'outer',
    'nonlocal',
    'extern'
  ], 2), // C

  createQuestion('py', 27, 'What is a decorator in Python?', [
    'A CSS stylesheet parser',
    'A tool for adding comments to documentation strings',
    'A class attribute validation rule',
    'A callable that takes another function as an argument and extends its behavior without modifying it'
  ], 3), // D

  createQuestion('py', 28, 'What is the main benefit of using a generator expression instead of a list comprehension?', [
    'Memory efficiency: values are produced on-demand (lazily) rather than allocating the entire list in RAM',
    'Generators run in parallel across multiple GPU cores',
    'Generators can only hold numeric values',
    'Generators allow random index-based lookups like `g[5]`'
  ], 0), // A

  createQuestion('py', 29, 'What does the `super()` function do in an inherited class method?', [
    'Calls the root Object class constructor only',
    'Returns a proxy object that delegates method calls to parent or sibling classes in the MRO',
    'Grants administrator privileges to the Python process',
    'Overrides all base class methods automatically'
  ], 1)  // B
];

// ----------------------------------------------------------------------------
// 3. JAVASCRIPT (30 MCQs)
// ----------------------------------------------------------------------------
export const JAVASCRIPT_MCQ_BANK = [
  createQuestion('js', 0, 'What is a closure in JavaScript?', [
    'A function that retains lexical scope access to variables in its outer environment even when invoked outside it',
    'A DOM method used to close modal dialogs',
    'A syntax construct that closes opened database connections',
    'A strict mode compiler error'
  ], 0), // A

  createQuestion('js', 1, 'What is the scoping difference between `let`/`const` and `var`?', [
    'var is block-scoped; let is global',
    'let and const are block-scoped; var is function-scoped (or globally scoped)',
    'const cannot be used inside loops',
    'var is evaluated at compile time; let is evaluated at runtime'
  ], 1), // B

  createQuestion('js', 2, 'What does `typeof null` evaluate to in JavaScript?', [
    '"null"',
    '"undefined"',
    '"object"',
    '"boolean"'
  ], 2), // C

  createQuestion('js', 3, 'What does `Promise.all()` do if any one promise in the input iterable rejects?', [
    'Returns null for the rejected item and continues the others',
    'Retries the rejected promise up to 3 times',
    'Waits for all other promises and returns an array of errors',
    'Immediately rejects with the error reason of the first rejected promise'
  ], 3), // D

  createQuestion('js', 4, 'Which method returns a new array containing elements that satisfy a provided test function?', [
    'Array.prototype.filter()',
    'Array.prototype.map()',
    'Array.prototype.forEach()',
    'Array.prototype.find()'
  ], 0), // A

  createQuestion('js', 5, 'What is the Event Loop in JavaScript runtime environments?', [
    'A for-loop that traverses all elements in the DOM tree',
    'A mechanism that monitors the call stack and moves tasks from the callback/microtask queue when the stack is empty',
    'A multi-threaded CPU scheduler that executes JavaScript across cores',
    'A garbage collection cycle triggered every 60 seconds'
  ], 1), // B

  createQuestion('js', 6, 'How do arrow functions handle the `this` binding?', [
    'They bind `this` to the global object unconditionally',
    'They create their own dynamic `this` context when invoked',
    'They retain the lexical `this` value of their enclosing execution context',
    'They throw a TypeError if `this` is referenced'
  ], 2), // C

  createQuestion('js', 7, 'What is the priority difference between Microtasks (e.g., Promise callbacks) and Macrotasks (e.g., setTimeout)?', [
    'Macrotasks execute before Microtasks in every event loop iteration',
    'Microtasks only execute when the browser window is resized',
    'They have identical priority and execute FIFO in a single queue',
    'Microtasks execute immediately after the current script and before the next Macrotask is processed'
  ], 3), // D

  createQuestion('js', 8, 'What is the purpose of the nullish coalescing operator (`??`)?', [
    'Returns its right-hand operand when its left-hand operand is null or undefined (not false or 0)',
    'Converts any truthy value into a boolean',
    'Performs logical bitwise NOR operations',
    'Catches runtime exceptions in async functions'
  ], 0), // A

  createQuestion('js', 9, 'What does `Object.freeze()` do to a JavaScript object?', [
    'Compresses the object in memory',
    'Prevents adding new properties, removing existing properties, or changing existing property values and configurability',
    'Converts the object to an immutable string',
    'Makes all functions inside the object private'
  ], 1), // B

  createQuestion('js', 10, 'Which array method reduces an array to a single accumulator value through a callback function?', [
    'filter()',
    'map()',
    'reduce()',
    'flat()'
  ], 2), // C

  createQuestion('js', 11, 'What is event bubbling in the browser DOM?', [
    'Events are dispatched only to the document root element',
    'Events randomly trigger on sibling elements',
    'Events cancel all subsequent event listeners',
    'An event triggers on the deepest target element and bubbles up through parent ancestors in the DOM tree'
  ], 3), // D

  createQuestion('js', 12, 'What does the optional chaining operator (`?.`) do?', [
    'Short-circuits and returns undefined if the reference before `?.` is null or undefined without throwing a TypeError',
    'Executes a method asynchronously in a web worker',
    'Performs optional string concatenation',
    'Creates a prototype chain link between two classes'
  ], 0), // A

  createQuestion('js', 13, 'What is the difference between `==` and `===` in JavaScript?', [
    '`==` compares memory addresses; `===` compares values',
    '`===` checks value and type without type coercion; `==` performs implicit type conversion before comparing',
    '`===` is only valid for strings and booleans',
    'There is no operational difference in modern V8 engines'
  ], 1), // B

  createQuestion('js', 14, 'What is variable hoisting in JavaScript?', [
    'Moving variables into localStorage automatically',
    'Deleting variables when they exit function scope',
    'The interpreter behavior of hoisting function and variable declarations to the top of their containing scope during compilation',
    'Converting local variables into global window properties'
  ], 2), // C

  createQuestion('js', 15, 'What is a key difference between `localStorage` and `sessionStorage`?', [
    'localStorage is stored on the server; sessionStorage is client-side',
    'sessionStorage has a 5GB quota; localStorage has 5MB',
    'localStorage only stores encrypted binary buffers',
    'localStorage persists across browser restarts until cleared; sessionStorage is cleared when the browser tab/session closes'
  ], 3), // D

  createQuestion('js', 16, 'What does `Promise.allSettled()` return when passed an array of promises?', [
    'A promise that resolves after all given promises have either fulfilled or rejected, with an array describing each result',
    'A promise that rejects immediately if any promise fails',
    'An array of values excluding any rejected errors',
    'A single cancelled promise'
  ], 0), // A

  createQuestion('js', 17, 'What is the difference between debounce and throttle utility functions?', [
    'Throttle delays execution until user stops typing; debounce runs at steady intervals',
    'Debounce delays execution until a quiet period of inactivity; throttle guarantees execution at most once per fixed time interval',
    'Debounce runs on background threads; throttle runs on the UI thread',
    'Throttle is only used for keyboard events; debounce is for scroll events'
  ], 1), // B

  createQuestion('js', 18, 'What is the output of `0.1 + 0.2 === 0.3` in JavaScript?', [
    'True',
    'TypeError',
    'False (due to IEEE-754 floating-point precision representation)',
    'NaN'
  ], 2), // C

  createQuestion('js', 19, 'What is the primary feature of a `WeakMap` in JavaScript?', [
    'It allows numeric keys only',
    'Keys can be enumerated using `for...of`',
    'Values are sorted automatically',
    'Keys must be objects, and they are weakly referenced so they can be garbage-collected if no other references exist'
  ], 3), // D

  createQuestion('js', 20, 'What does the spread operator (`...`) do when used in an array literal `[...arr1, ...arr2]`?', [
    'Expands elements of the iterables into the new array',
    'Calculates the dot product of both arrays',
    'Compresses both arrays into a single string',
    'Creates a circular reference between both arrays'
  ], 0), // A

  createQuestion('js', 21, 'How do you handle errors in an `async/await` function?', [
    'Using `catch` block outside the function only',
    'Wrapping asynchronous operations in a standard `try...catch` block',
    'Passing an error callback as the last argument',
    'Async functions never throw exceptions'
  ], 1), // B

  createQuestion('js', 22, 'What does `Array.prototype.map()` return?', [
    'A boolean indicating if all elements passed a condition',
    'The first matching element',
    'A new array containing the results of calling the provided function on every element',
    'The mutated original array in place'
  ], 2), // C

  createQuestion('js', 23, 'What does `NaN === NaN` evaluate to in JavaScript?', [
    'True',
    '1',
    'null',
    'False (NaN is the only value in JavaScript that is not equal to itself)'
  ], 3), // D

  createQuestion('js', 24, 'What is the purpose of `Function.prototype.bind()`?', [
    'Creates a new function that, when called, has its `this` keyword set to the provided value and preset initial arguments',
    'Executes the function immediately and returns its result',
    'Attaches an event listener to a DOM node',
    'Compiles the function into native machine code'
  ], 0), // A

  createQuestion('js', 25, 'What does the `JSON.stringify()` function do?', [
    'Parses a JSON string into a JavaScript object',
    'Converts a JavaScript value to a valid JSON formatted string',
    'Encrypts an object using SHA-256',
    'Validates JSON syntax without formatting'
  ], 1), // B

  createQuestion('js', 26, 'In modern JavaScript, what keyword imports exported members from another ES module?', [
    'require',
    'include',
    'import',
    'using'
  ], 2), // C

  createQuestion('js', 27, 'What does `document.querySelector()` return if no element matches the specified selector?', [
    'An empty NodeList',
    'undefined',
    'Throws a DOMException',
    'null'
  ], 3), // D

  createQuestion('js', 28, 'What is the prototype chain in JavaScript?', [
    'A delegation mechanism where objects inherit properties and methods from their prototype object up to Object.prototype',
    'A security sandbox that prevents cross-origin requests',
    'A linked list of active event listeners',
    'A list of functions compiled into WebAssembly'
  ], 0), // A

  createQuestion('js', 29, 'What does `requestAnimationFrame()` do in browser applications?', [
    'Loads CSS keyframe animations from external stylesheets',
    'Tells the browser you wish to perform an animation and requests that the browser call a specified callback function before the next repaint',
    'Renders 3D graphics using WebGL hardware acceleration',
    'Slows down video playback to match frame rates'
  ], 1)  // B
];

// ----------------------------------------------------------------------------
// 4. JAVA (30 MCQs)
// ----------------------------------------------------------------------------
export const JAVA_MCQ_BANK = [
  createQuestion('java', 0, 'What is the key difference between `final`, `finally`, and `finalize()` in Java?', [
    '`final` is an immutability modifier, `finally` is an exception block, and `finalize()` was a garbage collection callback',
    'All three are identical keyword aliases in Java bytecode',
    '`finally` creates immutable collections; `final` handles runtime errors',
    '`finalize()` is the modern alternative to try-with-resources'
  ], 0), // A

  createQuestion('java', 1, 'Which JVM memory area holds class metadata, method bytecode, and static variables in modern Java (8+)?', [
    'Thread Stack space',
    'Metaspace (native process memory)',
    'Permanent Generation (PermGen)',
    'Eden young generation space'
  ], 1), // B

  createQuestion('java', 2, 'What happens when two distinct objects produce the same `hashCode()` in a `HashMap`?', [
    'The second object replaces the first object silently',
    'The JVM throws an uncaught HashCollisionException',
    'A hash collision occurs, and entries are stored in a linked list or red-black tree within that bucket',
    'The map automatically doubles its capacity immediately'
  ], 2), // C

  createQuestion('java', 3, 'What guarantee does the `volatile` keyword provide for variables accessed by multiple threads?', [
    'Mutual exclusion: only one thread can execute methods on the object',
    'Atomic compound operations such as count++',
    'Prevents the garbage collector from freeing the variable',
    'Visibility: reads and writes go directly to main memory rather than thread CPU caches'
  ], 3), // D

  createQuestion('java', 4, 'Which interface represents a task that can be executed concurrently and returns a result or throws an exception?', [
    'Callable<V>',
    'Runnable',
    'Thread',
    'Completer'
  ], 0), // A

  createQuestion('java', 5, 'What is the internal data structure difference between `ArrayList` and `LinkedList` in Java?', [
    'ArrayList uses binary trees; LinkedList uses arrays',
    'ArrayList uses a dynamic resizable array; LinkedList uses doubly-linked nodes',
    'LinkedList is synchronized; ArrayList is not',
    'ArrayList only supports integers; LinkedList supports any object'
  ], 1), // B

  createQuestion('java', 6, 'What is the difference between Checked and Unchecked exceptions in Java?', [
    'Unchecked exceptions can never be caught; Checked exceptions can',
    'Checked exceptions inherit from Error; Unchecked exceptions inherit from Throwable',
    'Checked exceptions inherit from Exception and must be caught or declared; Unchecked inherit from RuntimeException and do not require explicit declaration',
    'There is no difference in compiler handling'
  ], 2), // C

  createQuestion('java', 7, 'Why is the `String` class immutable in Java?', [
    'To prevent strings from consuming heap memory',
    'To allow strings to be edited directly in CPU registers',
    'Because Java does not support array resizing',
    'For security, caching in the String Constant Pool, thread safety, and predictable hash code calculation'
  ], 3), // D

  createQuestion('java', 8, 'What is the difference between `StringBuilder` and `StringBuffer`?', [
    'StringBuilder is non-synchronized (faster, single-threaded); StringBuffer is synchronized (thread-safe)',
    'StringBuffer is non-synchronized; StringBuilder is thread-safe',
    'StringBuilder is immutable; StringBuffer is mutable',
    'StringBuffer cannot append integers'
  ], 0), // A

  createQuestion('java', 9, 'What is Type Erasure in Java Generics?', [
    'Deleting compiled .class files after classloading',
    'The compiler replaces all generic type parameters with their bounds (or Object) during compilation, so bytecode contains no generic types at runtime',
    'Converting object references to primitive memory addresses',
    'Allowing generic classes to hold primitive types directly'
  ], 1), // B

  createQuestion('java', 10, 'Which functional interface method signature matches `Predicate<T>` in `java.util.function`?', [
    'void accept(T t)',
    'R apply(T t)',
    'boolean test(T t)',
    'T get()'
  ], 2), // C

  createQuestion('java', 11, 'What is the purpose of the `try-with-resources` statement introduced in Java 7?', [
    'To automatically catch all runtime errors silently',
    'To retry database transactions up to 3 times',
    'To create lightweight virtual threads',
    'To automatically close any resource implementing `AutoCloseable` at the end of the block'
  ], 3), // D

  createQuestion('java', 12, 'What does the `default` keyword signify inside a Java 8+ interface?', [
    'Allows defining a concrete method implementation directly inside an interface without breaking backward compatibility',
    'Specifies package-private access modifier for the interface',
    'Sets the default return value of all interface methods to null',
    'Prevents classes from overriding the interface method'
  ], 0), // A

  createQuestion('java', 13, 'What is the difference between `Comparable` and `Comparator` interfaces in Java?', [
    'Comparator defines natural ordering inside the class; Comparable defines custom external ordering',
    '`Comparable` defines natural ordering via `compareTo()`; `Comparator` defines alternate custom ordering strategies via `compare()`',
    'Comparable is only for primitive types; Comparator is for collections',
    'Comparable was deprecated in Java 8'
  ], 1), // B

  createQuestion('java', 14, 'What is the difference between `equals()` and `==` when comparing two Java objects?', [
    '`==` compares object fields; `equals()` compares class names',
    '`equals()` is an operator; `==` is a method',
    '`==` checks reference identity (memory address); `equals()` checks logical value equivalence if overridden',
    'Both check reference identity unconditionally'
  ], 2), // C

  createQuestion('java', 15, 'What does the `synchronized` keyword achieve when applied to a method in Java?', [
    'Executes the method concurrently across all CPU cores',
    'Prevents the method from modifying any class variables',
    'Forces the method to return a CompletableFuture',
    'Acquires an intrinsic lock (monitor) on the instance or Class object, ensuring mutual exclusion among threads'
  ], 3), // D

  createQuestion('java', 16, 'What is a `record` in modern Java (Java 14+ / 16+)?', [
    'A concise class declaration for immutable data carriers with automatic constructor, getters, equals(), hashCode(), and toString()',
    'A direct interface to an SQL database row',
    'A mutable struct allocated on the thread call stack',
    'A sound recording media player component in JavaFX'
  ], 0), // A

  createQuestion('java', 17, 'What is the purpose of the `Optional<T>` class in Java 8+?', [
    'To replace all nullable fields in entity databases',
    'To provide a type-level solution for representing the presence or absence of a value without returning null',
    'To make method parameters optional in function calls',
    'To speed up garbage collection of unused objects'
  ], 1), // B

  createQuestion('java', 18, 'Which Stream API operation transforms elements of a stream into another type?', [
    'filter()',
    'distinct()',
    'map()',
    'peek()'
  ], 2), // C

  createQuestion('java', 19, 'What is the role of the ClassLoader in the Java Virtual Machine?', [
    'Compiles Java source files into bytecode',
    'Executes garbage collection on the heap',
    'Monitors thread synchronization locks',
    'Dynamically loads compiled Java bytecode (.class files) into the JVM memory space during runtime'
  ], 3), // D

  createQuestion('java', 20, 'What is the contract between `equals()` and `hashCode()` in Java?', [
    'If two objects are equal according to `equals()`, they must produce the same `hashCode()` value',
    'If two objects produce the same `hashCode()`, they must be equal according to `equals()`',
    '`hashCode()` is only required for immutable objects',
    'Overriding `equals()` automatically overrides `hashCode()` in compiled bytecode'
  ], 0), // A

  createQuestion('java', 21, 'Which access modifier grants accessibility to members within the same package and subclasses in other packages?', [
    'private',
    'protected',
    'public',
    'default (package-private)'
  ], 1), // B

  createQuestion('java', 22, 'What is the primary benefit of using `ExecutorService` rather than creating manual `new Thread()` instances?', [
    'Threads created by ExecutorService run without memory overhead',
    'ExecutorService bypasses JVM security checks',
    'Thread pooling: reuses existing worker threads, avoiding expensive thread creation and destruction overhead',
    'ExecutorService makes all code execute synchronously'
  ], 2), // C

  createQuestion('java', 23, 'What does the JVM JIT (Just-In-Time) compiler do?', [
    'Transpiles Java code to C++ before compilation',
    'Validates security certificates of JAR files',
    'Generates API documentation from JavaDoc comments',
    'Compiles frequently executed bytecode hot-spots into native machine code at runtime for performance'
  ], 3), // D

  createQuestion('java', 24, 'What is autoboxing in Java?', [
    'The automatic conversion that the Java compiler makes between primitive types and their corresponding object wrapper classes',
    'Packaging Java classes into JAR archives automatically',
    'Encapsulating private variables inside public getters',
    'Allocating heap memory using boxing algorithms'
  ], 0), // A

  createQuestion('java', 25, 'What is the difference between `throw` and `throws` keywords in Java?', [
    'They are identical keywords with different spellings',
    '`throw` is used to explicitly throw an exception object; `throws` is used in method signatures to declare exceptions',
    '`throws` is used inside catch blocks; `throw` is used in method signatures',
    '`throw` catches checked exceptions; `throws` catches unchecked exceptions'
  ], 1), // B

  createQuestion('java', 26, 'Which design pattern is implemented by `java.lang.Runtime.getRuntime()`?', [
    'Factory Method',
    'Observer',
    'Singleton',
    'Builder'
  ], 2), // C

  createQuestion('java', 27, 'What is a daemon thread in Java?', [
    'A high-priority thread that runs real-time kernel operations',
    'A thread that cannot be terminated by the operating system',
    'A thread that executes C library code via JNI',
    'A low-priority background thread that does not prevent the JVM from exiting when all user threads finish'
  ], 3), // D

  createQuestion('java', 28, 'What is the difference between an abstract class and an interface in Java 8+?', [
    'An abstract class can have instance state (fields) and constructors; an interface cannot maintain instance state',
    'Interfaces can only have private methods; abstract classes cannot',
    'A class can extend multiple abstract classes but implement only one interface',
    'Abstract classes cannot have concrete method implementations'
  ], 0), // A

  createQuestion('java', 29, 'What is reflection in Java?', [
    'Reflecting object states across network sockets',
    'The ability of a program to inspect, examine, and modify its own structure, classes, methods, and fields at runtime',
    'A graphic rendering technique in Java 2D',
    'A hardware mirroring technique for dual-core CPUs'
  ], 1)  // B
];

// ----------------------------------------------------------------------------
// 5. SQL & RELATIONAL DATABASES (30 MCQs)
// ----------------------------------------------------------------------------
export const SQL_MCQ_BANK = [
  createQuestion('sql', 0, 'What is the primary difference between WHERE and HAVING clauses in SQL?', [
    'WHERE filters rows before aggregation; HAVING filters groups after aggregation',
    'WHERE is for numeric data; HAVING is for text strings',
    'HAVING can only be used with subqueries',
    'WHERE requires an explicit GROUP BY clause'
  ], 0), // A

  createQuestion('sql', 1, 'What is the difference between an INNER JOIN and a LEFT OUTER JOIN?', [
    'LEFT JOIN excludes rows where foreign keys are null; INNER JOIN keeps them',
    'INNER JOIN returns matching rows from both tables; LEFT JOIN returns all rows from the left table plus matches from the right',
    'LEFT JOIN is faster because it bypasses table indexes',
    'Both return identical results on indexed relational tables'
  ], 1), // B

  createQuestion('sql', 2, 'Which index structure is standard for handling range queries (e.g., BETWEEN, <, >) in relational engines?', [
    'Hash Index',
    'Bitmap Vector',
    'B-Tree / B+ Tree',
    'Bloom Filter'
  ], 2), // C

  createQuestion('sql', 3, 'In ACID properties, what does "Isolation" ensure during concurrent transactions?', [
    'Transactions are permanently written to non-volatile storage',
    'Transactions execute on a single isolated CPU core',
    'Database tables cannot have cross-database foreign keys',
    'Uncommitted changes from one transaction cannot adversely affect or be observed by concurrent transactions'
  ], 3), // D

  createQuestion('sql', 4, 'What does the `COALESCE()` function return in SQL queries?', [
    'The first non-NULL expression from its argument list',
    'The statistical median of a column',
    'A concatenated string of all non-empty columns',
    'The total row count of the table'
  ], 0), // A

  createQuestion('sql', 5, 'What is the difference between `UNION` and `UNION ALL` in SQL?', [
    'UNION is only for integers; UNION ALL is for text',
    'UNION removes duplicate rows (sorting/deduplicating); UNION ALL preserves all duplicate rows and is faster',
    'UNION ALL reverses the sort order of rows',
    'UNION can only combine two tables; UNION ALL can combine ten'
  ], 1), // B

  createQuestion('sql', 6, 'What is a primary key constraint in a relational database?', [
    'An index that encrypts table rows with an AES key',
    'A column that must store auto-incrementing integers only',
    'A column or combination of columns that uniquely identifies each row and cannot contain NULL values',
    'A foreign reference to a parent table'
  ], 2), // C

  createQuestion('sql', 7, 'What does the `EXPLAIN` or `EXPLAIN ANALYZE` command provide in PostgreSQL/MySQL?', [
    'Translates SQL queries into natural language explanations for end users',
    'Checks the spelling of column and table identifiers',
    'Exports table schemas as JSON documentation',
    'The execution plan showing how the database optimizer plans to execute the query (scans, joins, costs, indexes)'
  ], 3), // D

  createQuestion('sql', 8, 'What is a Common Table Expression (CTE) in SQL?', [
    'A temporary named result set defined within the execution scope of a single SELECT, INSERT, UPDATE, or DELETE query using WITH',
    'A permanent database table shared across all user sessions',
    'An encrypted database connection channel',
    'A stored procedure that compiles to machine code'
  ], 0), // A

  createQuestion('sql', 9, 'What is the purpose of the `ROW_NUMBER()` window function?', [
    'Counts the total rows in the entire database',
    'Assigns a unique, sequential integer to each row within a partition, ordered by the specified ORDER BY clause',
    'Returns the physical disk offset of the row record',
    'Deletes duplicate rows from the table'
  ], 1), // B

  createQuestion('sql', 10, 'What is a clustered index in database storage engines like MySQL InnoDB?', [
    'An index created on multiple cloud cluster servers',
    'An index that stores only boolean columns',
    'An index where table rows are physically stored in the same order as the index key (the primary key in InnoDB)',
    'An in-memory hash map that disappears on server reboot'
  ], 2), // C

  createQuestion('sql', 11, 'Which transaction isolation level prevents Dirty Reads, Non-Repeatable Reads, and Phantom Reads completely?', [
    'Read Uncommitted',
    'Read Committed',
    'Repeatable Read',
    'Serializable'
  ], 3), // D

  createQuestion('sql', 12, 'What does the `FOREIGN KEY` constraint enforce in relational database design?', [
    'Referential integrity: ensures values in the child column must match existing values in the parent table primary key (or be NULL)',
    'Encrypts table relationships using foreign SSL certificates',
    'Prevents foreign IP addresses from querying the table',
    'Restricts table access to international regions'
  ], 0), // A

  createQuestion('sql', 13, 'What is database normalization (specifically 3NF - Third Normal Form)?', [
    'Combining all tables into a single wide table to eliminate JOINs',
    'Organizing columns and tables so every non-key column depends strictly on the primary key, the whole key, and nothing but the key (no transitive dependencies)',
    'Compressing disk tables into gzip format',
    'Adding duplicate columns to optimize read performance'
  ], 1), // B

  createQuestion('sql', 14, 'What is the difference between `DROP TABLE` and `TRUNCATE TABLE`?', [
    'DROP TABLE is faster; TRUNCATE deletes table permissions',
    'TRUNCATE can be filtered with a WHERE clause; DROP cannot',
    'DROP TABLE removes the data AND the table definition; TRUNCATE deletes all rows while keeping the table structure intact',
    'TRUNCATE deletes rows one by one firing all triggers; DROP does not'
  ], 2), // C

  createQuestion('sql', 15, 'What is the SQL function `NULLIF(val1, val2)` used for?', [
    'Converts NULL values to empty strings',
    'Replaces null foreign keys with 0',
    'Checks if both values are valid numbers',
    'Returns NULL if val1 equals val2; otherwise returns val1 (frequently used to prevent divide-by-zero errors)'
  ], 3), // D

  createQuestion('sql', 16, 'What does the LIKE pattern "A%_B" match in standard SQL?', [
    'Strings starting with "A", followed by any characters, then at least one character, ending with "B"',
    'Strings containing only the characters A and B',
    'Strings that start with an underscore',
    'Exact match of the literal string "A%_B"'
  ], 0), // A

  createQuestion('sql', 17, 'What is a database view?', [
    'A graphical user interface tool for database administration',
    'A virtual table based on the result-set of an underlying SQL query that dynamically runs when queried',
    'A backup snapshot saved to cloud storage',
    'A physical replica table updated every 24 hours'
  ], 1), // B

  createQuestion('sql', 18, 'What is the purpose of database transactions and the `ROLLBACK` command?', [
    'To reinstall the database software after a crash',
    'To permanently delete old audit logs',
    'To undo all database changes made during the current transaction if an error occurs, maintaining data consistency',
    'To reverse the order of returned rows'
  ], 2), // C

  createQuestion('sql', 19, 'What is SQL Injection, and how is it primarily prevented in enterprise applications?', [
    'A hardware failure where RAM corrupts SQL queries; prevented with ECC memory',
    'An unauthorized user deleting tables using SSH; prevented with firewalls',
    'A compiler bug in SQL parsing; prevented by upgrading database versions',
    'An attack where malicious SQL is injected into queries; prevented by using Parameterized Queries (Prepared Statements)'
  ], 3), // D

  createQuestion('sql', 20, 'What does `COUNT(*)` return compared to `COUNT(column_name)`?', [
    '`COUNT(*)` counts all rows including NULLs; `COUNT(column_name)` counts only rows where the specified column is non-NULL',
    '`COUNT(*)` counts only distinct rows; `COUNT(col)` counts all rows',
    '`COUNT(column_name)` is deprecated in ANSI SQL',
    'Both return identical results in all circumstances'
  ], 0), // A

  createQuestion('sql', 21, 'What is a Materialized View in databases like PostgreSQL or Oracle?', [
    'A view that can only be queried by root administrators',
    'A database view whose query results are physically stored on disk and can be refreshed periodically for high-performance reporting',
    'A temporary view created inside stored procedures',
    'A virtual view generated in JavaScript'
  ], 1), // B

  createQuestion('sql', 22, 'What does `CROSS JOIN` produce between Table A (5 rows) and Table B (4 rows)?', [
    '9 rows',
    '1 row',
    '20 rows (Cartesian product of all combinations)',
    '0 rows'
  ], 2), // C

  createQuestion('sql', 23, 'Which constraint prevents deleting a parent row when child rows exist, unless explicitly configured with `ON DELETE CASCADE`?', [
    'CHECK constraint',
    'NOT NULL constraint',
    'UNIQUE constraint',
    'FOREIGN KEY constraint'
  ], 3), // D

  createQuestion('sql', 24, 'What is the difference between `RANK()` and `DENSE_RANK()` window functions?', [
    '`RANK()` leaves gaps in ranking numbers after duplicate values; `DENSE_RANK()` assigns consecutive ranks without gaps',
    '`DENSE_RANK()` sorts in descending order; `RANK()` sorts in ascending order',
    '`RANK()` only works with numeric values; `DENSE_RANK()` works with text',
    '`DENSE_RANK()` requires an explicit partition by clause'
  ], 0), // A

  createQuestion('sql', 25, 'What does the `ON CONFLICT` clause (or `UPSERT`) do in PostgreSQL?', [
    'Terminates database connections that conflict with locks',
    'Specifies alternative action (e.g., DO NOTHING or DO UPDATE) when an INSERT violates a unique constraint or primary key',
    'Sends an email alert to the database administrator',
    'Automatically drops conflicting tables'
  ], 1), // B

  createQuestion('sql', 26, 'Why can an index on a column slow down `INSERT` and `UPDATE` operations?', [
    'Because indexes disable caching in RAM',
    'Because indexes lock the entire database table during writes',
    'Because every insert or update requires the database engine to also update the index tree structure and rebalance nodes',
    'Indexes do not affect write operations'
  ], 2), // C

  createQuestion('sql', 27, 'Which clause is used to paginate SQL query results by skipping a specified number of rows?', [
    'SKIP',
    'JUMP',
    'PAGE',
    'OFFSET'
  ], 3), // D

  createQuestion('sql', 28, 'What is a database deadlock?', [
    'A situation where two or more transactions are blocked waiting for locks held by each other, creating a circular dependency',
    'A physical disk failure preventing database startup',
    'A server crash caused by out-of-memory errors',
    'A query that takes longer than 30 seconds to execute'
  ], 0), // A

  createQuestion('sql', 29, 'What does the `CHECK` constraint do in an SQL table definition?', [
    'Checks if the database server has enough disk space',
    'Specifies a boolean condition that all inserted or updated values in that column must satisfy',
    'Validates user passwords against hashing algorithms',
    'Automatically audits all SELECT queries on the table'
  ], 1)  // B
];

// ----------------------------------------------------------------------------
// 6. FRONTEND WEB ARCHITECTURE & HTML/CSS (30 MCQs)
// ----------------------------------------------------------------------------
export const HTML_CSS_MCQ_BANK = [
  createQuestion('html', 0, 'What is the primary benefit of using semantic HTML5 elements (<header>, <main>, <nav>, <article>)?', [
    'Provides landmark regions for screen readers and search engines, improving accessibility and SEO',
    'Forces the browser to render with GPU acceleration',
    'Prevents CSS styles from bleeding across components',
    'Automatically transpiles JavaScript code'
  ], 0), // A

  createQuestion('html', 1, 'Under `box-sizing: border-box`, what does an element\'s declared width include?', [
    'Content width only',
    'Content width + padding + border',
    'Content width + margin',
    'Padding and margin only'
  ], 1), // B

  createQuestion('html', 2, 'In CSS Flexbox, which property aligns items along the cross axis?', [
    'justify-content',
    'flex-direction',
    'align-items',
    'order'
  ], 2), // C

  createQuestion('html', 3, 'What is the WCAG 2.1 AA minimum contrast requirement for standard body text?', [
    '3:1',
    '7:1',
    '1.5:1',
    '4.5:1'
  ], 3), // D

  createQuestion('html', 4, 'Which CSS media query selects viewport widths of 768px or smaller for mobile responsive layouts?', [
    '@media (max-width: 768px)',
    '@media (min-width: 768px)',
    '@media screen and (device-width: 768px)',
    '@media (orientation: portrait)'
  ], 0), // A

  createQuestion('html', 5, 'What is the CSS specificity order from highest to lowest?', [
    'Element selector > Class selector > ID selector > Inline styles',
    'Inline styles > ID selector > Class/Attribute/Pseudo-class selector > Element selector',
    'ID selector > Inline styles > Class selector > Universal selector',
    'Class selector > Element selector > ID selector > Inline styles'
  ], 1), // B

  createQuestion('html', 6, 'What is the difference between `rem` and `em` units in CSS?', [
    '`rem` is relative to viewport width; `em` is relative to viewport height',
    '`rem` is only for margins; `em` is only for font sizes',
    '`rem` is relative to the root (`<html>`) element font-size; `em` is relative to the font-size of its immediate parent',
    'There is no difference; both calculate identically'
  ], 2), // C

  createQuestion('html', 7, 'What does `position: absolute` do relative to its containing block in CSS?', [
    'Positions the element relative to the browser viewport even during scroll',
    'Places the element in the normal document flow',
    'Locks the element to the bottom right corner of the screen',
    'Removes the element from normal flow and positions it relative to its closest positioned ancestor (position not static)'
  ], 3), // D

  createQuestion('html', 8, 'What is the purpose of the `<meta name="viewport" content="width=device-width, initial-scale=1.0">` tag?', [
    'Sets the screen width to match device width and sets initial zoom level, enabling responsive mobile rendering',
    'Disables user pinch-to-zoom on all touchscreens',
    'Forces high-DPI retina rendering on desktop monitors',
    'Specifies the character encoding for the HTML document'
  ], 0), // A

  createQuestion('html', 9, 'What is the difference between `display: none` and `visibility: hidden` in CSS?', [
    '`display: none` makes the element translucent; `visibility: hidden` deletes it',
    '`display: none` removes the element from layout space completely; `visibility: hidden` hides it but preserves its physical layout space',
    '`visibility: hidden` disables JavaScript click events; `display: none` does not',
    '`display: none` is only valid for inline elements'
  ], 1), // B

  createQuestion('html', 10, 'Which CSS Grid property defines the number and sizing of columns in a grid layout?', [
    'grid-column-gap',
    'grid-auto-flow',
    'grid-template-columns',
    'grid-template-rows'
  ], 2), // C

  createQuestion('html', 11, 'Why is using `aria-label` or `<label for="inputId">` essential for form input fields?', [
    'To apply automatic CSS border styling when invalid',
    'To allow password managers to auto-fill credit cards',
    'To submit form data via AJAX without page reloads',
    'To ensure assistive technologies (screen readers) announce an accessible name for the input control'
  ], 3), // D

  createQuestion('html', 12, 'What does the CSS pseudo-class `:focus-visible` do?', [
    'Applies focus styles only when the user navigates via keyboard or assistive tech, avoiding unwanted focus rings on mouse click',
    'Applies styles when an element is hovered with a mouse cursor',
    'Reveals hidden passwords in form input fields',
    'Forces an element to remain focused permanently'
  ], 0), // A

  createQuestion('html', 13, 'What does the `loading="lazy"` attribute on an `<img>` element achieve?', [
    'Applies a blur animation while the image downloads',
    'Defers downloading the offscreen image until the user scrolls near the viewport, saving network bandwidth and memory',
    'Compresses the image file size by 50%',
    'Converts PNG images to WebP format dynamically'
  ], 1), // B

  createQuestion('html', 14, 'What is a CSS stacking context, and what primarily creates one?', [
    'A CSS preprocessor compilation order created by SASS',
    'A method to stack flex items vertically created by `flex-direction: column`',
    'A 3D conceptualization of HTML elements along the z-axis, created by properties like opacity < 1, transform, or position with z-index',
    'A tool for managing multiple CSS stylesheets'
  ], 2), // C

  createQuestion('html', 15, 'What is the purpose of the `alt` attribute on an `<img>` tag in HTML?', [
    'Displays a tooltip when hovering over the image',
    'Specifies the image dimensions in pixels',
    'Defines the fallback image URL if the primary image fails',
    'Provides descriptive alternative text for screen readers and users when the image fails to load'
  ], 3), // D

  createQuestion('html', 16, 'How do CSS custom properties (variables) declare and evaluate in standard CSS?', [
    'Declared with `--variable-name: value;` and retrieved with `var(--variable-name)`',
    'Declared with `$variable-name: value;` and retrieved with `eval($variable-name)`',
    'Declared with `@def variable-name: value;` and retrieved with `get(variable-name)`',
    'Declared with `#variable-name: value;` and retrieved with `val(variable-name)`'
  ], 0), // A

  createQuestion('html', 17, 'What does `position: sticky` do in CSS?', [
    'Permanently locks an element to the center of the screen',
    'Toggles between relative and fixed positioning based on the user\'s scroll position relative to its scrolling container',
    'Makes elements stick to cursor drag movements',
    'Prevents elements from ever being scrolled out of view'
  ], 1), // B

  createQuestion('html', 18, 'Which HTML5 element represents an independent, self-contained composition (e.g., blog post, news story)?', [
    '<section>',
    '<div>',
    '<article>',
    '<aside>'
  ], 2), // C

  createQuestion('html', 19, 'What is the Critical Rendering Path in browser performance optimization?', [
    'The network path traversed by optical fiber cables',
    'The order in which HTML tags are validated by the W3C linter',
    'The timeline of database queries executed on the backend',
    'The sequence of steps the browser takes from receiving HTML/CSS/JS to painting pixels on the screen (DOM -> CSSOM -> Render Tree -> Layout -> Paint)'
  ], 3), // D

  createQuestion('html', 20, 'What is the purpose of the `srcset` attribute on `<img>` tags?', [
    'Provides multiple image sources and resolution descriptors so the browser selects the optimal image based on screen DPI and viewport width',
    'Specifies an array of animated GIF frames',
    'Allows fallback images in case the primary image is blocked by ad blockers',
    'Defines the SVG vector path coordinates'
  ], 0), // A

  createQuestion('html', 21, 'What is the recommended minimum touch target size according to mobile accessibility guidelines?', [
    '16px by 16px',
    '44px by 44px (or 48px by 48px)',
    '100px by 100px',
    '24px by 24px'
  ], 1), // B

  createQuestion('html', 22, 'What does the CSS property `flex-grow: 1` signify for a flex child item?', [
    'The item scales up by 100% using CSS transform',
    'The item font size increases by 1rem',
    'The item will expand to take up any remaining available space along the main axis in the flex container',
    'The item shrinks when viewport decreases'
  ], 2), // C

  createQuestion('html', 23, 'Which HTML attribute specifies that an `<input>` field must be completed before submitting a form?', [
    'mandatory="true"',
    'validate',
    'enforce',
    'required'
  ], 3), // D

  createQuestion('html', 24, 'What is the effect of `overflow: hidden` on a container with floats?', [
    'Establishes a new block formatting context (BFC), containing floated child elements without extra clearfix markup',
    'Deletes floated elements from the DOM tree',
    'Displays horizontal and vertical scrollbars permanently',
    'Centers the container in the middle of the viewport'
  ], 0), // A

  createQuestion('html', 25, 'What is the difference between `<button type="button">` and `<button type="submit">`?', [
    'type="button" cannot have click listeners; type="submit" can',
    'type="submit" submits the containing form by default; type="button" has no default action until scripted',
    'type="submit" can only be clicked once; type="button" can be clicked multiple times',
    'There is no behavioral difference in modern browsers'
  ], 1), // B

  createQuestion('html', 26, 'Which CSS property creates smooth transitions between property changes without JavaScript?', [
    'animation-fill-mode',
    'transform-style',
    'transition',
    'will-change'
  ], 2), // C

  createQuestion('html', 27, 'Why should developers avoid setting `user-scalable=no` or `maximum-scale=1` in the viewport meta tag?', [
    'It prevents desktop browser resizing',
    'It causes CSS flexbox layouts to fail',
    'It reduces the CPU performance of mobile browsers',
    'It disables pinch-to-zoom, severely harming accessibility for users with visual impairments'
  ], 3), // D

  createQuestion('html', 28, 'What is the purpose of the `<picture>` element in HTML5 responsive design?', [
    'Allows developers to define multiple source images for different media query conditions (art direction) with an `<img>` fallback',
    'Integrates webcam photo capture capabilities into web forms',
    'Converts 2D images into 3D models',
    'Displays image EXIF metadata and GPS coordinates'
  ], 0), // A

  createQuestion('html', 29, 'What does `z-index: 9999` do if the element has `position: static`?', [
    'Brings the element to the front of all windows',
    'Has no effect, because z-index only applies to positioned elements (relative, absolute, fixed, sticky) or flex/grid items',
    'Causes a layout error in strict CSS mode',
    'Forces GPU hardware acceleration'
  ], 1)  // B
];

// ----------------------------------------------------------------------------
// 7. UI/UX DESIGN & DESIGN SYSTEMS (30 MCQs)
// ----------------------------------------------------------------------------
export const DESIGN_MCQ_BANK = [
  createQuestion('ux', 0, 'Under Nielsen Norman usability heuristics, what is the purpose of "Visibility of System Status"?', [
    'Keep users informed about what is occurring through appropriate and timely feedback within a reasonable time',
    'Display server CPU utilization in the website footer',
    'Show all database schemas to the end user',
    'Ensure the company brand logo is visible on every viewport'
  ], 0), // A

  createQuestion('ux', 1, 'What is the primary difference between a wireframe and a high-fidelity prototype?', [
    'Wireframes are built with HTML/CSS; prototypes are static images',
    'Wireframes establish structural layout and information architecture; prototypes provide interactive fidelity and visual styling',
    'Prototypes are only produced after production launch',
    'There is no difference; the terms are interchangeable'
  ], 1), // B

  createQuestion('ux', 2, 'What does Fitts\'s Law predict regarding user interface target acquisition?', [
    'User attention drops exponentially after 3 seconds of page load',
    'Colors with higher saturation always receive higher click-through rates',
    'Target acquisition time decreases as target size increases and movement distance decreases',
    'Users scan content strictly in a clockwise circular motion'
  ], 2), // C

  createQuestion('ux', 3, 'What is the recommended approach for error prevention in form design?', [
    'Clear all user inputs when validation fails to force complete re-entry',
    'Display error codes without descriptive user-facing explanations',
    'Disable form submission until the page is refreshed',
    'Provide clear constraints, real-time inline validation, and confirmation for destructive actions'
  ], 3), // D

  createQuestion('ux', 4, 'What is the primary purpose of conducting a "think-aloud" usability study?', [
    'To observe users\' cognitive models, misconceptions, and points of friction in real time as they complete tasks',
    'To collect quantitative server response times',
    'To train users on how to navigate the final product',
    'To test browser memory limits during video recording'
  ], 0), // A

  createQuestion('ux', 5, 'What does Hick\'s Law state regarding decision time in user experience design?', [
    'Users always prefer more options over fewer options',
    'The time it takes to make a decision increases logarithmically with the number and complexity of choices',
    'Every user interface must have exactly 3 navigation items',
    'Decisions made on mobile devices are 50% faster than desktop'
  ], 1), // B

  createQuestion('ux', 6, 'What is Jakob\'s Law of Internet User Experience?', [
    'Websites must use dark mode by default',
    'Animations should never exceed 200 milliseconds',
    'Users spend most of their time on other sites, so they prefer your site to work the same way as all the other sites they already know',
    'Search bars must always be positioned in the bottom left'
  ], 2), // C

  createQuestion('ux', 7, 'In Atomic Design methodology, what are the five hierarchical stages of interface construction?', [
    'Pixels, Vectors, Components, Layouts, Applications',
    'Styles, Tokens, Themes, Pages, Exports',
    'HTML, CSS, JavaScript, Frameworks, Servers',
    'Atoms, Molecules, Organisms, Templates, Pages'
  ], 3), // D

  createQuestion('ux', 8, 'What is the purpose of design tokens in a cross-platform design system?', [
    'Platform-agnostic key-value pairs (colors, spacing, typography) that synchronize design decisions across Figma, Web, iOS, and Android',
    'Cryptographic authentication tokens used for user login',
    'Icons displayed in the browser navigation bar',
    'Payment tokens used for checkout verification'
  ], 0), // A

  createQuestion('ux', 9, 'What does Miller\'s Law state regarding human working memory capacity?', [
    'Users can remember up to 50 items simultaneously if presented in bullet points',
    'The average human working memory can hold approximately 7 (plus or minus 2) chunks of information at a time',
    'Users lose memory retention after 7 seconds of inactivity',
    'Webpages should have no more than 7 words per paragraph'
  ], 1), // B

  createQuestion('ux', 10, 'What is a "dark pattern" in user interface design?', [
    'A high-contrast dark theme optimized for OLED screens',
    'A design pattern used for military and defense software',
    'A deceptive user interface deliberately crafted to trick users into doing things they might not otherwise choose to do',
    'An unstyled wireframe using black and gray shapes'
  ], 2), // C

  createQuestion('ux', 11, 'Why are skeleton loaders preferred over traditional spinning loaders for content loading?', [
    'Skeleton loaders use less GPU memory than spinning SVGs',
    'Skeleton loaders automatically translate content into multiple languages',
    'They allow users to click buttons before data finishes loading',
    'They reduce perceived waiting time by indicating the visual structure and layout of upcoming content'
  ], 3), // D

  createQuestion('ux', 12, 'What does the usability heuristic "Recognition rather than recall" advise for UX designers?', [
    'Minimize user memory load by making objects, actions, and options visible or easily retrievable rather than requiring recall from memory',
    'Force users to take a quiz before unlocking new product features',
    'Require biometric face recognition for every login',
    'Use ambiguous abstract iconography to stimulate user curiosity'
  ], 0), // A

  createQuestion('ux', 13, 'What is the primary objective of Card Sorting research in UX design?', [
    'To evaluate credit card checkout processing speeds',
    'To understand how users categorize information and organize site navigation hierarchy (information architecture)',
    'To test user reaction speeds with digital playing cards',
    'To sort database tables into alphabetical order'
  ], 1), // B

  createQuestion('ux', 14, 'What is a user persona in product design?', [
    'The legal identity of a verified enterprise customer',
    'An anonymized record stored in user analytics databases',
    'A semi-fictional archetype representing the key traits, goals, motivations, and pain points of a specific user segment',
    'A cartoon avatar used in customer service chat widgets'
  ], 2), // C

  createQuestion('ux', 15, 'What is the System Usability Scale (SUS), and what score represents an above-average usability benchmark?', [
    'A scale measuring server uptime; benchmark is 99.9%',
    'A scale measuring design file size; benchmark is 100MB',
    'A scale measuring font readability; benchmark is 16px',
    'A standardized 10-item questionnaire measuring usability perception; a score of 68 is the historical industry average'
  ], 3), // D

  createQuestion('ux', 16, 'What does the heuristic "Flexibility and efficiency of use" suggest for expert users?', [
    'Provide accelerators (such as keyboard shortcuts, macros, and customizable workflows) that speed up interaction for experienced users',
    'Hide all advanced settings behind administrator permissions',
    'Make the interface change layout dynamically every session',
    'Remove all buttons and replace them with voice commands'
  ], 0), // A

  createQuestion('ux', 17, 'What is progressive disclosure in user interface design?', [
    'Showing all available advanced features and configuration options on a single screen',
    'Sequencing information and actions across multiple steps, showing only what is necessary at each stage to reduce cognitive overload',
    'Gradually increasing font size as users read down a page',
    'Revealing paid subscription pricing after account creation'
  ], 1), // B

  createQuestion('ux', 18, 'What is the primary role of micro-interactions in digital product design?', [
    'To execute micro-payments on blockchain ledgers',
    'To reduce web browser CPU utilization',
    'To provide subtle visual, auditory, or haptic feedback that confirms actions, rewards users, and communicates status',
    'To log analytics telemetry events silently'
  ], 2), // C

  createQuestion('ux', 19, 'What does WCAG 2.1 AA requirement state regarding non-text contrast (such as button boundaries and form input borders)?', [
    'Minimum 1.5:1 contrast against adjacent colors',
    'Minimum 7:1 contrast against adjacent colors',
    'Contrast is not required if the element has a drop shadow',
    'Minimum 3:1 contrast ratio against adjacent background colors'
  ], 3), // D

  createQuestion('ux', 20, 'What is the purpose of Auto Layout in Figma design workflows?', [
    'Creates dynamic frames that respond to content changes, resizing buttons, lists, and cards automatically with defined padding and gap',
    'Automatically generates production React code from shapes',
    'Aligns design shapes to the Golden Ratio formula',
    'Exports raster images directly to iOS App Store'
  ], 0), // A

  createQuestion('ux', 21, 'What is an "empty state" (or zero data state) in UX design?', [
    'A blank white screen shown during a server crash',
    'A purposeful screen shown when no data exists (e.g., first login, empty cart), guiding users on how to populate data and take next steps',
    'A modal dialog warning users about expired sessions',
    'A wireframe without typography'
  ], 1), // B

  createQuestion('ux', 22, 'What does the heuristic "Consistency and standards" help users avoid?', [
    'Reading documentation manuals',
    'Submitting forms with invalid credit cards',
    'Wondering whether different words, situations, or actions mean the same thing across different platform screens',
    'Experiencing network latency on mobile connections'
  ], 2), // C

  createQuestion('ux', 23, 'Why should designers avoid using color alone to convey critical state (e.g., green for success, red for error)?', [
    'Because color monitors consume more battery than monochrome',
    'Because CSS styles may fail to load over slow networks',
    'Because modern operating systems disable color in high contrast mode',
    'To ensure color-blind users can perceive status through supplementary indicators like icons, text labels, and patterns'
  ], 3), // D

  createQuestion('ux', 24, 'What is an empathy map in design research?', [
    'A collaborative visualization tool used to articulate what we know about a user type, split into Says, Thinks, Does, and Feels',
    'A GPS map tracking user locations during usability field tests',
    'A heat map recording user mouse hover trajectories',
    'A chart showing customer sentiment ratings over time'
  ], 0), // A

  createQuestion('ux', 25, 'What is the difference between quantitative and qualitative user research?', [
    'Quantitative studies are done in labs; qualitative studies are done remotely',
    'Quantitative research answers "How many / How much" using numerical metrics; Qualitative research answers "Why / How" using behavioral observations',
    'Qualitative research is only for marketing; Quantitative is for engineering',
    'There is no distinction in modern agile sprints'
  ], 1), // B

  createQuestion('ux', 26, 'What does the "Aesthetic and minimalist design" heuristic advise?', [
    'Interfaces must be completely monochrome with zero imagery',
    'Interfaces should only use standard system fonts',
    'Dialogues should not contain information that is irrelevant or rarely needed, as every extra unit of information competes with relevant information',
    'Buttons must not have rounded corners'
  ], 2), // C

  createQuestion('ux', 27, 'What is an "accordion" UI component, and when is it best utilized?', [
    'A music playback widget in web audio players',
    'A full-screen modal that forces user confirmation',
    'A 3D image carousel that auto-rotates every 5 seconds',
    'A vertically stacked list of headers that expand/collapse to reveal associated content, ideal for organizing dense content like FAQs'
  ], 3), // D

  createQuestion('ux', 28, 'What is a cognitive walkthrough in usability inspection?', [
    'A method where evaluators step through a sequence of user tasks asking specific questions about user intent, actions, and feedback at each step',
    'An EEG scan measuring user brain waves during mobile phone usage',
    'A walking interview conducted in the user\'s workplace',
    'An automated AI robot navigating a prototype'
  ], 0), // A

  createQuestion('ux', 29, 'What is a "Breadcrumb" trail in website navigation?', [
    'A cookie tracking user browsing history across external domains',
    'A secondary navigation scheme that reveals the user\'s location in a website or web app hierarchy and allows navigating up levels',
    'A loading progress bar shown in the page header',
    'A list of recently viewed product items in an ecommerce store'
  ], 1)  // B
];

// ----------------------------------------------------------------------------
// 8. GENERAL SOFTWARE ENGINEERING & SYSTEM ARCHITECTURE (30 MCQs)
// ----------------------------------------------------------------------------
export const GENERAL_MCQ_BANK = [
  createQuestion('gen', 0, 'What is the primary architectural goal of modularity in software engineering?', [
    'To isolate responsibilities, minimize tight coupling, and enhance testability and maintainability',
    'To maximize CPU clock speed on single-core devices',
    'To eliminate the need for version control repositories',
    'To bypass build validation checks'
  ], 0), // A

  createQuestion('gen', 1, 'Which metric best indicates consistent code quality and operational reliability?', [
    'Total lines of code written per sprint',
    'Comprehensive automated test coverage and reproducible build pipelines',
    'Number of third-party libraries installed in package.json',
    'Frequency of emergency deployment hotfixes'
  ], 1), // B

  createQuestion('gen', 2, 'What is the role of Continuous Integration (CI) in engineering teams?', [
    'Deploying code directly to production without testing',
    'Manually inspecting database schemas once a quarter',
    'Automating code linting, tests, and build verification on every commit or pull request',
    'Managing cloud billing accounts'
  ], 2), // C

  createQuestion('gen', 3, 'How should edge cases and invalid inputs be handled in production software?', [
    'Silently swallow errors and return null without logging',
    'Assume callers will always provide well-formed arguments',
    'Crash the entire host process unconditionally',
    'Validate early at module boundaries and return explicit error states, exceptions, or validation results'
  ], 3), // D

  createQuestion('gen', 4, 'What is the core principle of iterative software delivery?', [
    'Delivering increments of verified working functionality with continuous user and stakeholder feedback',
    'Planning all implementation details in advance for 2 years without adjustments',
    'Deploying code once a year in a single giant release',
    'Writing all documentation before writing any code'
  ], 0), // A

  createQuestion('gen', 5, 'What does the Single Responsibility Principle (SRP) in SOLID state?', [
    'Every programmer should work on only one file per sprint',
    'A class or module should have one, and only one, reason to change (a single cohesive responsibility)',
    'All functions must have exactly one line of code',
    'An application should run on a single server instance'
  ], 1), // B

  createQuestion('gen', 6, 'What is the difference between authentication and authorization?', [
    'Authentication determines permissions; authorization determines identity',
    'They are synonymous terms in web security',
    'Authentication verifies WHO you are (identity); authorization determines WHAT you are allowed to access (permissions)',
    'Authentication is handled by databases; authorization is handled by DNS'
  ], 2), // C

  createQuestion('gen', 7, 'What is Technical Debt in software systems?', [
    'The monetary cost of cloud computing bills',
    'The salary paid to junior software developers',
    'The unpaid licensing fees for open-source libraries',
    'The implied cost of additional rework caused by choosing an easy or expedient solution now instead of using a better approach that takes longer'
  ], 3), // D

  createQuestion('gen', 8, 'What is the DRY (Don\'t Repeat Yourself) principle aimed at reducing?', [
    'Repetition of software patterns and logic, replacing duplicate code with abstractions or data normalization to avoid divergence bugs',
    'The amount of documentation written in README files',
    'The number of git commits made by developers',
    'The RAM consumption of compiled binaries'
  ], 0), // A

  createQuestion('gen', 9, 'What is the primary benefit of containerization using technologies like Docker?', [
    'Containers eliminate the need for writing unit tests',
    'Consistency across environments: packages application code and dependencies into isolated, reproducible containers that run reliably anywhere',
    'Containers run code directly on bare-metal hardware without an OS',
    'Containers automatically optimize SQL queries'
  ], 1), // B

  createQuestion('gen', 10, 'In RESTful API design, which HTTP method is considered idempotent and safe for reading resources without side effects?', [
    'POST',
    'DELETE',
    'GET',
    'PATCH'
  ], 2), // C

  createQuestion('gen', 11, 'What is the Open-Closed Principle (OCP) in object-oriented design?', [
    'Databases should be open to reads but closed to writes',
    'Source code must be open-source and closed to commercial use',
    'Network ports should be closed unless explicitly opened by firewalls',
    'Software entities (classes, modules, functions) should be open for extension, but closed for modification'
  ], 3), // D

  createQuestion('gen', 12, 'What is the difference between concurrency and parallelism?', [
    'Concurrency is about dealing with a lot of things at once (structure); parallelism is about doing a lot of things at once (simultaneous execution on multiple cores)',
    'Concurrency is only for multi-core CPUs; parallelism is for single-core CPUs',
    'Parallelism is software-based; concurrency is hardware-based',
    'They are identical terms in operating system design'
  ], 0), // A

  createQuestion('gen', 13, 'What is Semantic Versioning (SemVer: MAJOR.MINOR.PATCH)?', [
    'MAJOR = bug fixes, MINOR = security patches, PATCH = breaking changes',
    'MAJOR = breaking API changes, MINOR = backwards-compatible new features, PATCH = backwards-compatible bug fixes',
    'MAJOR = year, MINOR = month, PATCH = day',
    'A versioning convention used only for database tables'
  ], 1), // B

  createQuestion('gen', 14, 'What is the role of an API Gateway in microservices architecture?', [
    'Compiles microservices into a single monolith executable',
    'Stores user passwords in an encrypted database table',
    'A single entry point that handles request routing, authentication, rate limiting, and telemetry before passing requests to internal microservices',
    'Replaces frontend web applications entirely'
  ], 2), // C

  createQuestion('gen', 15, 'What does the Circuit Breaker pattern prevent in distributed systems?', [
    'High electrical voltage in server room hardware',
    'Unencrypted network packets from leaking across firewalls',
    'Users from accessing expired credit cards',
    'Cascading failures: temporarily stops invoking a failing downstream service to allow it time to recover rather than overloading it with requests'
  ], 3), // D

  createQuestion('gen', 16, 'What is Test-Driven Development (TDD) cycle commonly referred to as?', [
    'Red-Green-Refactor (write failing test, write minimal code to pass, refactor clean code)',
    'Plan-Build-Deploy',
    'Draft-Review-Approve',
    'Lint-Compile-Execute'
  ], 0), // A

  createQuestion('gen', 17, 'What is the primary difference between horizontal scaling and vertical scaling?', [
    'Horizontal scaling adds faster CPU/RAM to a single server; vertical scaling adds more servers',
    'Horizontal scaling adds more machine nodes to a pool; vertical scaling upgrades CPU, RAM, or storage of an existing machine',
    'Vertical scaling is cheaper than horizontal scaling at scale',
    'Horizontal scaling requires downtime; vertical scaling never does'
  ], 1), // B

  createQuestion('gen', 18, 'What is the purpose of rate limiting in web APIs?', [
    'To measure internet bandwidth speed between countries',
    'To force users to upgrade their browsers',
    'To control the rate of incoming requests to prevent abuse, DoS attacks, and resource starvation across users',
    'To sort API responses by date'
  ], 2), // C

  createQuestion('gen', 19, 'What is the principle of least privilege in cybersecurity?', [
    'All users should be given root administrator privileges to avoid friction',
    'Security rules should only be applied to external contractors',
    'Passwords must be rotated every 7 days',
    'Users, processes, and programs should be granted only the minimum permissions and access necessary to perform their required tasks'
  ], 3), // D

  createQuestion('gen', 20, 'What is a cache invalidation strategy commonly referred to by Martin Fowler?', [
    '"There are only two hard things in Computer Science: cache invalidation and naming things."',
    '"Always cache every database query in RAM permanently."',
    '"Caches should only store static HTML files."',
    '"Cache invalidation is automated by operating system kernels."'
  ], 0), // A

  createQuestion('gen', 21, 'What is the Liskov Substitution Principle (LSP) in SOLID?', [
    'Classes should never have subclasses',
    'Subtypes must be substitutable for their base types without altering the correctness of the program',
    'Functions must not accept more than two arguments',
    'Database rows can be substituted with JSON files'
  ], 1), // B

  createQuestion('gen', 22, 'What are the three pillars of observability in modern distributed systems?', [
    'HTML, CSS, JavaScript',
    'CPU, Memory, Disk',
    'Metrics, Logs, and Distributed Traces',
    'Security, Compliance, and Performance'
  ], 2), // C

  createQuestion('gen', 23, 'What is the purpose of an index in database systems?', [
    'To encrypt sensitive user passwords',
    'To prevent duplicate rows from being inserted into any table',
    'To store table backups in cold storage',
    'A data structure that speeds up data retrieval operations on a database table at the cost of additional storage and slower writes'
  ], 3), // D

  createQuestion('gen', 24, 'What is trunk-based development in version control workflows?', [
    'A practice where developers merge small, frequent updates directly into a single central branch ("trunk" or "main"), avoiding long-lived feature branches',
    'Storing all git repositories on physical external hard drives',
    'A branching strategy where every developer works in isolation for 6 months',
    'A tree-like database structure for storing git objects'
  ], 0), // A

  createQuestion('gen', 25, 'What is the difference between a synchronous and an asynchronous API call?', [
    'Synchronous calls run on GPU; asynchronous calls run on CPU',
    'Synchronous calls block execution until a response is received; asynchronous calls initiate the operation and allow program execution to continue while waiting',
    'Asynchronous calls cannot return data; synchronous calls can',
    'Synchronous calls are only used in mobile applications'
  ], 1), // B

  createQuestion('gen', 26, 'What does the Dependency Inversion Principle (DIP) state?', [
    'Low-level modules should depend on high-level modules',
    'All dependencies must be imported dynamically at runtime',
    'High-level modules should not depend on low-level modules; both should depend on abstractions (interfaces)',
    'Dependencies should be hardcoded directly into class constructors'
  ], 2), // C

  createQuestion('gen', 27, 'What is CORS (Cross-Origin Resource Sharing) in web browsers?', [
    'A protocol for compressing images over slow networks',
    'A database query optimization technique',
    'A video streaming format used by YouTube',
    'A browser security mechanism that uses HTTP headers to tell browsers whether a web application running at one origin has permission to access resources from a different origin'
  ], 3), // D

  createQuestion('gen', 28, 'What is idempotency in distributed systems and REST APIs?', [
    'An operation that produces the same system state whether it is executed once or multiple times consecutively (e.g., PUT, DELETE)',
    'An operation that executes in zero milliseconds',
    'An algorithm that encrypts database passwords',
    'A server that cannot be rebooted'
  ], 0), // A

  createQuestion('gen', 29, 'What is the difference between unit testing and integration testing?', [
    'Integration testing is done by end users; unit testing is done by automated tools',
    'Unit testing tests individual functions or classes in isolation; integration testing tests how multiple components or services interact together',
    'Unit testing requires a live database; integration testing does not',
    'There is no functional distinction between them'
  ], 1)  // B
];

export const ALL_MCQ_BANKS = {
  c: C_MCQ_BANK,
  python: PYTHON_MCQ_BANK,
  javascript: JAVASCRIPT_MCQ_BANK,
  java: JAVA_MCQ_BANK,
  sql: SQL_MCQ_BANK,
  html: HTML_CSS_MCQ_BANK,
  design: DESIGN_MCQ_BANK,
  general: GENERAL_MCQ_BANK
};
