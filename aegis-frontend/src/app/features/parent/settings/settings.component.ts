import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ThemeService } from '../../../core/services/theme.service';
import { THEME_PRESETS, type ThemePreset } from '../../admin/settings/settings.data';
import { AuthService } from '../../../core/services/auth.service';
import { ApiService } from '../../../core/services/api.service';
import { OnInit } from '@angular/core';

// Reusable components
import { PageHeaderComponent } from '@shared/index';
import { SelectModule } from 'primeng/select';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';

@Component({
  selector: 'app-parent-settings',
  standalone: true,
  imports: [
    CommonModule, 
    FormsModule, 
    PageHeaderComponent, 
    SelectModule, 
    ToggleSwitchModule, 
    ToastModule
  ],
  providers: [MessageService],
  templateUrl: './settings.html',
  styleUrls: ['./settings.css']
})
export class SettingsComponent implements OnInit {
  private themeService = inject(ThemeService);
  private messageService = inject(MessageService);
  private authService = inject(AuthService);
  private apiService = inject(ApiService);

  // Theme State
  themePresets = THEME_PRESETS;
  currentThemeId = this.themeService.selectedThemeId;
  darkMode = this.themeService.darkMode;
  
  selectedTheme = this.themePresets.find(p => p.id === this.currentThemeId()) || this.themePresets[0];

  // Parent Notification Preferences
  notifications = signal({
    emailNotifications: true,
    inAppNotifications: true,
    notifyOnBlock: true,
    notifyOnWarn: false,
    quietHoursStart: '22:00',
    quietHoursEnd: '07:00'
  });

  // Parent Account Profile
  parentAccount = signal({
    displayName: '',
    email: '',
    monitoringMode: 'child',
    trustedContactName: '',
    trustedContactPhone: '',
    lastLogin: new Date().toLocaleString()
  });

  ngOnInit() {
    this.authService.currentUser$.subscribe(user => {
      if (user) {
        this.parentAccount.update(p => ({
          ...p,
          displayName: `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username,
          email: user.email || '',
          monitoringMode: user.monitoring_mode || 'child',
          trustedContactName: user.trusted_contact_name || '',
          trustedContactPhone: user.trusted_contact_phone || ''
        }));
      }
    });
  }

  // Password change state
  showPasswordForm = signal(false);
  passwordForm = signal({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });

  // --- Theme Handlers ---
  selectTheme(themeId: string) {
    const preset = this.themePresets.find(t => t.id === themeId);
    if (preset) {
      this.selectedTheme = preset;
      this.themeService.selectTheme(themeId as any);
    }
  }

  toggleDarkMode(isDark: boolean) {
    this.themeService.toggleDarkMode(isDark);
  }

  // --- Notification Handlers ---
  updateNotification(key: keyof ReturnType<typeof this.notifications>, value: any) {
    this.notifications.update(n => ({ ...n, [key]: value }));
  }

  // --- Profile Handlers ---
  updateParentAccount(key: keyof ReturnType<typeof this.parentAccount>, value: string) {
    this.parentAccount.update(p => ({ ...p, [key]: value }));
  }

  togglePasswordForm() {
    this.showPasswordForm.update(v => !v);
    if (!this.showPasswordForm()) {
      this.passwordForm.set({ currentPassword: '', newPassword: '', confirmPassword: '' });
    }
  }

  updatePasswordField(key: keyof ReturnType<typeof this.passwordForm>, value: string) {
    this.passwordForm.update(f => ({ ...f, [key]: value }));
  }

  savePassword() {
    if (!this.passwordForm().currentPassword || !this.passwordForm().newPassword) {
      this.messageService.add({ severity: 'error', summary: 'Error', detail: 'All password fields are required.' });
      return;
    }
    if (this.passwordForm().newPassword !== this.passwordForm().confirmPassword) {
      this.messageService.add({ severity: 'error', summary: 'Error', detail: 'New passwords do not match.' });
      return;
    }

    this.apiService.updateCurrentUser({
      password: this.passwordForm().newPassword,
      current_password: this.passwordForm().currentPassword,
    }).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Password updated successfully.' });
        this.togglePasswordForm();
      },
      error: (err) => {
        const detail = err?.error?.error || 'Failed to update password. Check your current password.';
        this.messageService.add({ severity: 'error', summary: 'Error', detail, life: 4000 });
      }
    });
  }

  saveSettings() {
    const a = this.parentAccount();
    const nameParts = a.displayName.split(' ');
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ') || '';

    this.apiService.updateCurrentUser({
      first_name: firstName,
      last_name: lastName,
      notification_email: a.email,
      monitoring_mode: a.monitoringMode,
      trusted_contact_name: a.trustedContactName,
      trusted_contact_phone: a.trustedContactPhone
    }).subscribe({
      next: () => {
        // Refresh user in auth service so other components see the change
        this.authService.fetchCurrentUser();
        this.messageService.add({ 
          severity: 'success', 
          summary: 'Settings Saved', 
          detail: 'Your preferences have been updated successfully.' 
        });
      },
      error: () => {
        this.messageService.add({ 
          severity: 'error', 
          summary: 'Save Failed', 
          detail: 'Could not update your account settings.' 
        });
      }
    });
  }
}

