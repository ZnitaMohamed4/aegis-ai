import { DOCUMENT } from '@angular/common';
import { inject, Injectable, signal } from '@angular/core';
import {
  DEFAULT_SETTINGS,
  THEME_PRESETS,
  THEME_VARIABLES,
  type ThemePreset,
} from '../../features/admin/settings/settings.data';

const STORAGE_KEY = 'aegis-theme-prefs';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);

  readonly selectedThemeId = signal<ThemePreset['id']>(DEFAULT_SETTINGS.appearance.selectedThemeId);
  readonly darkMode = signal(DEFAULT_SETTINGS.appearance.darkMode);

  constructor() {
    const saved = this.loadPrefs();
    if (saved) {
      this.selectedThemeId.set(saved.themeId);
      this.darkMode.set(saved.darkMode);
    }
    this.apply();
  }

  selectTheme(themeId: ThemePreset['id']): void {
    this.selectedThemeId.set(themeId);
    this.apply();
    this.savePrefs();
  }

  toggleDarkMode(enabled: boolean): void {
    this.darkMode.set(enabled);
    this.apply();
    this.savePrefs();
  }

  private apply(): void {
    const variables = THEME_VARIABLES[this.selectedThemeId()][this.darkMode() ? 'dark' : 'light'];
    const body = this.document.body;

    for (const [token, value] of Object.entries(variables)) {
      body.style.setProperty(token, value);
    }

    body.classList.toggle('dark', this.darkMode());
  }

  private savePrefs(): void {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ themeId: this.selectedThemeId(), darkMode: this.darkMode() })
      );
    } catch { /* storage unavailable */ }
  }

  private loadPrefs(): { themeId: ThemePreset['id']; darkMode: boolean } | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (parsed && THEME_PRESETS.some(p => p.id === parsed.themeId)) {
        return { themeId: parsed.themeId, darkMode: !!parsed.darkMode };
      }
      return null;
    } catch {
      return null;
    }
  }
}
