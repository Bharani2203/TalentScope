import { loadSkillCatalog } from '../../../api/intelligence-catalog-client.js';
import { loadIndividualOnboardingProfile } from '../../../onboarding/onboarding-api.js';

function cleanText(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function normalizeSkillLabel(value) {
  return cleanText(value).normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ');
}

function stringList(value) {
  return Array.isArray(value) ? value.map(cleanText).filter(Boolean) : [];
}

function buildSkillLookup(catalog) {
  const rows = Array.isArray(catalog?.skills) ? catalog.skills : [];
  const lookup = new Map();
  rows.forEach(row => {
    if (!row || typeof row.skill_id !== 'string' || typeof row.name !== 'string') return;
    [row.name, row.skill_id, ...(Array.isArray(row.aliases) ? row.aliases : [])]
      .map(normalizeSkillLabel)
      .filter(Boolean)
      .forEach(label => lookup.set(label, row));
  });
  return lookup;
}

export function normalizeLearningProfile(response, catalog = null) {
  const profile = response?.profile && typeof response.profile === 'object' ? response.profile : {};
  const answers = response?.answers && typeof response.answers === 'object' ? response.answers : {};
  const basic = profile.basic_profile && typeof profile.basic_profile === 'object' ? profile.basic_profile : {};
  const skillProfile = profile.skills && typeof profile.skills === 'object' ? profile.skills : {};
  const career = profile.career && typeof profile.career === 'object' ? profile.career : {};
  const experienceProfile = profile.experience && typeof profile.experience === 'object' ? profile.experience : {};
  const work = profile.work_preferences && typeof profile.work_preferences === 'object' ? profile.work_preferences : {};
  const rawSkills = stringList(skillProfile.selected_skills ?? answers.skills);
  const levels = skillProfile.skill_levels && typeof skillProfile.skill_levels === 'object'
    ? skillProfile.skill_levels
    : answers.skill_levels && typeof answers.skill_levels === 'object' ? answers.skill_levels : {};
  const lookup = buildSkillLookup(catalog);
  const registryAvailable = lookup.size > 0;
  const canonicalSkills = Array.isArray(catalog?.skills) ? catalog.skills
    .filter(row => row && typeof row.skill_id === 'string' && typeof row.name === 'string')
    .map(row => ({ skill_id: row.skill_id, name: row.name, aliases: Array.isArray(row.aliases) ? row.aliases.filter(alias => typeof alias === 'string') : [] })) : [];
  const seen = new Set();
  const skills = rawSkills.flatMap(rawName => {
    const canonical = lookup.get(normalizeSkillLabel(rawName));
    const identity = canonical?.skill_id || normalizeSkillLabel(rawName);
    if (!identity || seen.has(identity)) return [];
    seen.add(identity);
    const rawLevel = Object.entries(levels).find(([name]) => {
      const levelSkill = lookup.get(normalizeSkillLabel(name));
      return (levelSkill?.skill_id || normalizeSkillLabel(name)) === identity;
    })?.[1];
    const selfReportedLevel = cleanText(rawLevel);
    return [{
      skill_id: canonical?.skill_id || null,
      name: canonical?.name || rawName,
      declared_name: rawName,
      mapping_status: canonical ? 'canonical' : registryAvailable ? 'manual' : 'unverified',
      self_reported_level: selfReportedLevel || null,
      level_source: selfReportedLevel ? 'self_reported' : 'not_reported',
      assessment_level: null,
      assessment_status: 'not_assessed'
    }];
  });
  const goals = career.career_goals ?? answers.career_goal;
  const roles = career.target_roles ?? (answers.target_role ? [answers.target_role] : []);
  const interests = profile.interests ?? answers.interest_areas;
  const learningPreferences = profile.learning_preferences ?? answers.learning_style;
  const location = [cleanText(basic.city), cleanText(basic.country)].filter(Boolean).join(', ');
  const onboarding = response?.onboarding && typeof response.onboarding === 'object' ? response.onboarding : {};

  return {
    name: cleanText(basic.name) || cleanText(response?.display_name) || null,
    onboarding: {
      completed: onboarding.completed === true,
      current_step: Number.isInteger(onboarding.current_step) ? onboarding.current_step : null,
      completed_steps: Array.isArray(onboarding.completed_steps) ? onboarding.completed_steps : []
    },
    skills,
    target_role: stringList(roles)[0] || null,
    career_goals: stringList(goals),
    interests: stringList(interests),
    learning_preferences: stringList(learningPreferences),
    experience: cleanText(experienceProfile.experience) || cleanText(answers.experience?.experience) || null,
    study_field: cleanText(experienceProfile.studyField) || cleanText(answers.experience?.studyField) || null,
    location: location || null,
    weekly_learning_time: cleanText(work.learning_time) || cleanText(answers.weekly_time) || null,
    work_preference: cleanText(work.work_preference) || cleanText(answers.work_preference) || null,
    skill_registry_available: registryAvailable,
    skill_catalog: canonicalSkills
  };
}

export async function loadLearningProfileContext({ loadProfile = loadIndividualOnboardingProfile, loadCatalog = loadSkillCatalog } = {}) {
  const [profileResult, catalogResult] = await Promise.allSettled([loadProfile(), loadCatalog()]);
  if (profileResult.status === 'rejected') throw profileResult.reason;
  const catalog = catalogResult.status === 'fulfilled' ? catalogResult.value : null;
  return normalizeLearningProfile(profileResult.value, catalog);
}
