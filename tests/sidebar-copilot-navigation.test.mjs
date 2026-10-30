import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('AI Co-Pilot persistent slide-out drawer & sidebar removal verification', async () => {
  const [appSource, sidebarSource, individualNavSource, routerSource, layoutSource] = await Promise.all([
    readFile(new URL('../src/app/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/layout/Sidebar.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/portals/individual/navigation.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/app/router.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/layout/IndividualLayout.js', import.meta.url), 'utf8')
  ]);

  // 1. Verify "AI Co-Pilot" is REMOVED from the Sidebar menu
  assert.doesNotMatch(
    sidebarSource,
    /\{\s*label:\s*'AI Co-Pilot'/,
    'Sidebar.js component must NOT include AI Co-Pilot menu item'
  );

  // 2. Verify "AI Co-Pilot" is REMOVED from the individual navigation Workspace
  assert.doesNotMatch(
    individualNavSource,
    /\{\s*label:\s*'AI Co-Pilot'/,
    'individual/navigation.js must NOT include AI Co-Pilot in workspace navigation'
  );

  // 3. Verify "AI Co-Pilot" is REMOVED from app.js navigation structure
  assert.doesNotMatch(
    appSource,
    /\{\s*label:\s*'AI Co-Pilot',\s*icon:\s*'bot',\s*route:\s*'\/individual\/clean-help'\s*\}/,
    'app.js navigation array must NOT include AI Co-Pilot in sidebar navigation'
  );

  // 4. Verify IndividualLayout.js implements global chat state (useState)
  assert.match(
    layoutSource,
    /const\s*\[\s*isCopilotOpen\s*,\s*setIsCopilotOpen\s*\]\s*=\s*useState\s*\(\s*false\s*\)/,
    'IndividualLayout.js must implement const [isCopilotOpen, setIsCopilotOpen] = useState(false);'
  );

  // 5. Verify Floating Action Button (FAB) in the bottom-right corner with AI/bot icon
  assert.match(
    layoutSource,
    /id=["']copilotFab["']/,
    'IndividualLayout.js must render a Floating Action Button with id copilotFab'
  );
  assert.match(
    layoutSource,
    /setIsCopilotOpen\s*\(\s*!isCopilotOpen\s*\)/,
    'IndividualLayout.js FAB must attach onClick handler toggling isCopilotOpen'
  );

  // 6. Verify Persistent Slide-out Drawer mounted outside <Outlet />
  assert.match(
    layoutSource,
    /id=["']copilotSlideoutDrawer["']/,
    'IndividualLayout.js must render slide-out drawer with id copilotSlideoutDrawer'
  );
  assert.match(
    layoutSource,
    /transform:\s*isCopilotOpen\s*\?\s*['"]translateX\(0\)['"]\s*:\s*['"]translateX\(100%\)['"]/,
    'IndividualLayout.js drawer must slide horizontally via translateX based on isCopilotOpen'
  );
  assert.ok(
    layoutSource.indexOf('<Outlet') < layoutSource.indexOf('copilotSlideoutDrawer'),
    'Slide-out drawer must be mounted outside the main <Outlet /> to preserve conversation history'
  );

  // 7. Verify persistent drawer & FAB initialization in the live DOM app.js
  assert.match(
    appSource,
    /copilotSlideoutDrawer/,
    'app.js must create persistent copilotSlideoutDrawer outside mainContent'
  );
  assert.match(
    appSource,
    /floatingAiLauncher/,
    'app.js must render floating action button for AI Co-Pilot'
  );

  // 8. Verify legacy safety preserved
  assert.match(appSource, /\{ label: 'AI Assistant', icon: 'sparkles', route: '\/individual\/ai-assistant' \}/);
  assert.doesNotMatch(appSource, /label: 'AI Help', icon: 'messages-square', route: '\/individual\/ai-help'/);
});
