// Device-local onboarding and explanation preferences.

const KEYS = Object.freeze({
  profile: 'loomq.quantumProfile',
  explainConcepts: 'loomq.explainConcepts',
  conceptBasics: 'loomq.conceptBasics',
  exampleCircuit: 'loomq.exampleCircuit',
  onboardingComplete: 'loomq.onboardingComplete',
});

export class PreferenceStore {
  constructor(storage = window.localStorage) {
    this.storage = storage;
  }

  getLearningPreferences() {
    const profile = this.get(KEYS.profile) || '';
    const legacyExplain = this.get(KEYS.explainConcepts) === 'true';
    const storedBasics = this.get(KEYS.conceptBasics);
    const storedExample = this.get(KEYS.exampleCircuit);
    const profileDefaults = {
      new: { conceptBasics: true, exampleCircuit: true },
      some: { conceptBasics: false, exampleCircuit: true },
      expert: { conceptBasics: false, exampleCircuit: false },
    }[profile] || { conceptBasics: legacyExplain, exampleCircuit: legacyExplain };
    return {
      profile,
      explainConcepts: storedBasics === null ? profileDefaults.conceptBasics : storedBasics === 'true',
      conceptBasics: storedBasics === null ? profileDefaults.conceptBasics : storedBasics === 'true',
      exampleCircuit: storedExample === null ? profileDefaults.exampleCircuit : storedExample === 'true',
    };
  }

  saveLearningPreferences(profile, modules) {
    const conceptBasics = typeof modules === 'boolean' ? modules : modules.conceptBasics;
    const exampleCircuit = typeof modules === 'boolean' ? modules : modules.exampleCircuit;
    this.set(KEYS.profile, profile);
    this.set(KEYS.explainConcepts, String(conceptBasics));
    this.set(KEYS.conceptBasics, String(conceptBasics));
    this.set(KEYS.exampleCircuit, String(exampleCircuit));
  }

  isOnboardingComplete() {
    return this.get(KEYS.onboardingComplete) === 'true';
  }

  markOnboardingComplete() {
    this.set(KEYS.onboardingComplete, 'true');
  }

  get(key) {
    try {
      return this.storage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  set(key, value) {
    try {
      this.storage.setItem(key, value);
    } catch (_error) {
      // Preferences are optional; the app remains usable without browser storage.
    }
  }
}
