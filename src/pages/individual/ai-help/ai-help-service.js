/**
 * Local-only response provider for the AI Help UI.
 * Replace this module with an authenticated API client when real help integration is approved.
 * This provider never calls a model, remote service, or platform data source.
 */
export const AI_HELP_RESPONSE_MODE = 'demo';
export const AI_HELP_MAX_QUESTION_LENGTH = 1200;

const temporaryHelpTopics = [
  {
    match: /skill intelligence|my skills|skill gaps?/i,
    response: 'Temporary help response: Open My Skills from the left navigation to review Skill Intelligence. Company skill-gap workflows are available from Workforce for users with company access. This demo does not read or analyze your profile data.'
  },
  {
    match: /market intelligence|market insights/i,
    response: 'Temporary help response: Choose Market Insights in the Explore section of the left navigation. Use the available filters to focus the view. This demo cannot retrieve or summarize live market data.'
  },
  {
    match: /job opportunities|find jobs|career opportunities|job listings?/i,
    response: 'Temporary help response: Open Career from the Main section of the left navigation to explore career opportunities. This demo does not retrieve job listings or make recommendations.'
  },
  {
    match: /insufficient data/i,
    response: 'Temporary help response: “Insufficient data” means the available evidence did not meet the requirements for a reliable result. It does not mean the value is zero. Review the result’s evidence coverage and limitations for more context.'
  },
  {
    match: /navigate|navigation|platform/i,
    response: 'Temporary help response: Use the left navigation to open the main areas of TalentScope.ai. Notifications and AI Help are in the Workspace section. Menu items adapt to the portal and access available to your account.'
  }
];

const defaultTemporaryResponse = 'Temporary help response: I can explain how to find and use TalentScope.ai features. This demo does not access account records, live platform data, or external AI services. Try a question about Skill Intelligence, Market Insights, Career, or navigation.';

export async function getTemporaryHelpResponse(question) {
  if (typeof question !== 'string' || !question.trim()) {
    throw new TypeError('Enter a question before sending.');
  }

  const normalizedQuestion = question.trim();
  if (normalizedQuestion.length > AI_HELP_MAX_QUESTION_LENGTH) {
    throw new RangeError(`Keep your question to ${AI_HELP_MAX_QUESTION_LENGTH} characters or fewer.`);
  }

  // A small delay lets the UI show its loading state during local development.
  await new Promise(resolve => setTimeout(resolve, 350));
  const topic = temporaryHelpTopics.find(item => item.match.test(normalizedQuestion));

  return {
    text: topic?.response || defaultTemporaryResponse,
    mode: AI_HELP_RESPONSE_MODE,
    status: 'ok'
  };
}
