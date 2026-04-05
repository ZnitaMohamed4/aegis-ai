import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { Select } from 'primeng/select';
import { Toast } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { PageHeaderComponent } from '@shared/index';
import { ThemeService } from '@core/services/theme.service';
import {
  DEFAULT_SETTINGS,
  LANGUAGE_OPTIONS,
  THEME_PRESETS,
  type AdminAccountSettings,
  type ModerationDefaults,
  type NotificationDefaults,
  type RetentionSettings,
  type ThemePreset,
} from './settings.data';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, PageHeaderComponent, ToggleSwitch, Select, Toast],
  providers: [MessageService],
  templateUrl: './settings.html',
  styleUrl: './settings.css',
})
export class SettingsComponent {
  private readonly themeService = inject(ThemeService);
  private readonly messageService = inject(MessageService);

  readonly themePresets = THEME_PRESETS;
  readonly languageOptions = LANGUAGE_OPTIONS;

  readonly selectedThemeId = this.themeService.selectedThemeId;
  get selectedTheme() {
    return this.themePresets.find(t => t.id === this.selectedThemeId()) || this.themePresets[0];
  }
  readonly darkMode = this.themeService.darkMode;

  readonly retention = signal<RetentionSettings>({ ...DEFAULT_SETTINGS.retention });
  readonly notifications = signal<NotificationDefaults>({ ...DEFAULT_SETTINGS.notifications });
  readonly moderation = signal<ModerationDefaults>({ ...DEFAULT_SETTINGS.moderation });
  readonly adminAccount = signal<AdminAccountSettings>({ ...DEFAULT_SETTINGS.adminAccount });

  readonly showPasswordForm = signal(false);
  readonly passwordForm = signal({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  readonly showPurgeConfirmation = signal(false);

  selectTheme(themeId: ThemePreset['id']): void {
    this.themeService.selectTheme(themeId);
  }

  toggleDarkMode(enabled: boolean): void {
    this.themeService.toggleDarkMode(enabled);
  }

  updateRetention<K extends keyof RetentionSettings>(key: K, value: RetentionSettings[K]): void {
    this.retention.update((state) => ({ ...state, [key]: value }));
  }

  updateNotification<K extends keyof NotificationDefaults>(
    key: K,
    value: NotificationDefaults[K]
  ): void {
    this.notifications.update((state) => ({ ...state, [key]: value }));
  }

  updateModeration<K extends keyof ModerationDefaults>(
    key: K,
    value: ModerationDefaults[K]
  ): void {
    this.moderation.update((state) => ({ ...state, [key]: value }));
  }

  updateAdminAccount<K extends keyof AdminAccountSettings>(
    key: K,
    value: AdminAccountSettings[K]
  ): void {
    this.adminAccount.update((state) => ({ ...state, [key]: value }));
  }

  updatePasswordField(field: 'currentPassword' | 'newPassword' | 'confirmPassword', value: string): void {
    this.passwordForm.update((form) => ({ ...form, [field]: value }));
  }

  togglePasswordForm(): void {
    const next = !this.showPasswordForm();
    this.showPasswordForm.set(next);

    if (!next) {
      this.passwordForm.set({ currentPassword: '', newPassword: '', confirmPassword: '' });
    }
  }

  savePassword(): void {
    const { currentPassword, newPassword, confirmPassword } = this.passwordForm();

    if (!currentPassword || !newPassword || !confirmPassword) {
      this.messageService.add({
        severity: 'warn',
        summary: 'Incomplete',
        detail: 'Please complete all password fields before saving.',
        life: 3000,
      });
      return;
    }

    if (newPassword !== confirmPassword) {
      this.messageService.add({
        severity: 'error',
        summary: 'Mismatch',
        detail: 'New password and confirmation do not match.',
        life: 3000,
      });
      return;
    }

    this.messageService.add({
      severity: 'success',
      summary: 'Password Updated',
      detail: 'Your password has been changed successfully.',
      life: 3000,
    });
    this.passwordForm.set({ currentPassword: '', newPassword: '', confirmPassword: '' });
    this.showPasswordForm.set(false);
  }

  requestPurgeData(): void {
    this.showPurgeConfirmation.set(true);
  }

  cancelPurgeData(): void {
    this.showPurgeConfirmation.set(false);
  }

  confirmPurgeData(): void {
    this.showPurgeConfirmation.set(false);
    this.messageService.add({
      severity: 'info',
      summary: 'Data Purged',
      detail: 'All stored data has been purged in this demo environment.',
      life: 3000,
    });
  }

  saveSettings(): void {
    this.messageService.add({
      severity: 'success',
      summary: 'Settings Saved',
      detail: 'Your settings have been updated successfully.',
      life: 3000,
    });
  }
}
