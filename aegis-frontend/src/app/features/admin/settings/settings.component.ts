import { CommonModule } from '@angular/common';
import { Component, inject, signal, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { Select } from 'primeng/select';
import { Toast } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { PageHeaderComponent } from '@shared/index';
import { ThemeService } from '@core/services/theme.service';
import { ApiService } from '@core/services/api.service';
import { AuthService } from '@core/services/auth.service';
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
export class SettingsComponent implements OnInit {
  private readonly themeService = inject(ThemeService);
  private readonly messageService = inject(MessageService);
  private readonly apiService = inject(ApiService);
  private readonly authService = inject(AuthService);

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

  ngOnInit(): void {
    this.apiService.getSystemSettings().subscribe({
      next: (settings) => {
        this.retention.set({
          messagesLogDays: settings.log_retention_days,
          blockedMessagesDays: settings.message_retention_days,
          alertHistoryDays: settings.alert_retention_days,
          riskProfileHistoryDays: settings.risk_profile_retention_days ?? 60
        });
        this.notifications.set({
          emailNotifications: settings.notify_email_enabled ?? true,
          inAppNotifications: settings.notify_inapp_enabled ?? true,
          notifyOnBlock: settings.notify_on_block ?? true,
          notifyOnEscalate: settings.notify_on_escalate ?? true,
          notifyOnWarn: settings.notify_on_warn ?? false,
          quietHoursStart: settings.quiet_hours_start || '23:00',
          quietHoursEnd: settings.quiet_hours_end || '07:00',
        });
        this.moderation.set({
          ...this.moderation(),
          defaultLanguage: settings.default_language || 'auto',
          autoResolveAllow: settings.auto_resolve_allow ?? true,
          rateLimitThreshold: settings.rate_limit_threshold ?? 50,
          parentPortalAccess: settings.parent_portal_access ?? true,
          strictnessLevel: settings.strictness_level as any,
          autoEscalate: settings.auto_escalate,
          blockUnknown: settings.block_unknown
        } as any);
      },
      error: () => console.error('Failed to load system settings')
    });

    this.authService.currentUser$.subscribe(user => {
      if (user) {
        this.adminAccount.update(acc => ({
          ...acc,
          language: user.language_preference as any || 'en',
          phone: user.phone_number || '',
          email: user.notification_email || user.email || '',
          desktopNotifications: user.auto_protection_enabled || false
        }));
      }
    });
  }

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

    this.apiService.updateCurrentUser({
      password: newPassword,
      current_password: currentPassword,
    }).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Password Updated',
          detail: 'Your password has been changed successfully.',
          life: 3000,
        });
        this.passwordForm.set({ currentPassword: '', newPassword: '', confirmPassword: '' });
        this.showPasswordForm.set(false);
      },
      error: (err) => {
        const detail = err?.error?.error || 'Failed to update password. Check your current password.';
        this.messageService.add({
          severity: 'error',
          summary: 'Password Change Failed',
          detail,
          life: 4000,
        });
      }
    });
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
    const r = this.retention();
    const m = this.moderation();
    const n = this.notifications();
    const a = this.adminAccount();

    // 1. Save Platform Settings (retention + notifications + moderation + risk retention)
    const platformPayload: any = {
      log_retention_days: r.messagesLogDays,
      message_retention_days: r.blockedMessagesDays,
      alert_retention_days: r.alertHistoryDays,
      risk_profile_retention_days: r.riskProfileHistoryDays,
      strictness_level: (m as any).strictnessLevel || 'balanced',
      auto_escalate: (m as any).autoEscalate ?? true,
      block_unknown: (m as any).blockUnknown ?? false,
      // Notification defaults
      notify_email_enabled: n.emailNotifications,
      notify_inapp_enabled: n.inAppNotifications,
      notify_on_block: n.notifyOnBlock,
      notify_on_escalate: n.notifyOnEscalate,
      notify_on_warn: n.notifyOnWarn,
      quiet_hours_start: n.quietHoursStart,
      quiet_hours_end: n.quietHoursEnd,
      // Extended moderation defaults
      default_language: (m as any).defaultLanguage || 'auto',
      auto_resolve_allow: (m as any).autoResolveAllow ?? true,
      rate_limit_threshold: (m as any).rateLimitThreshold ?? 50,
      parent_portal_access: (m as any).parentPortalAccess ?? true,
    };
    
    this.apiService.updateSystemSettings(platformPayload).subscribe({
      next: () => console.log('Platform settings updated'),
      error: (err) => console.error('Failed to update platform settings', err)
    });

    // 2. Save User Settings
    const userPayload = {
      language_preference: a.language,
      phone_number: a.phone,
      notification_email: a.email,
      auto_protection_enabled: a.desktopNotifications
    };

    this.apiService.updateCurrentUser(userPayload).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Settings Saved',
          detail: 'Your settings have been updated successfully.',
          life: 3000,
        });
      },
      error: (err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Save Failed',
          detail: 'Failed to update your account settings.',
          life: 3000,
        });
      }
    });
  }
}
