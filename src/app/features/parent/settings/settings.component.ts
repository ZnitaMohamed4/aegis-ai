import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ThemeService } from '../../../core/services/theme.service';
import { THEME_PRESETS, type ThemePreset } from '../../admin/settings/settings.data';

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
export class SettingsComponent {
  private themeService = inject(ThemeService);
  private messageService = inject(MessageService);

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
    displayName: 'Emma\'s Dad',
    email: 'parent@example.com',
    lastLogin: new Date().toLocaleString()
  });

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
    
    this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Password updated successfully.' });
    this.togglePasswordForm();
  }

  // Save everything else
  saveSettings() {
    // In a real app, you'd dispatch an update to a backend here
    this.messageService.add({ 
      severity: 'success', 
      summary: 'Settings Saved', 
      detail: 'Your preferences have been updated successfully.' 
    });
  }
}

