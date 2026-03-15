import { Component, EventEmitter, inject, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThemeService } from '@core/services/theme.service';

@Component({
  selector: 'app-topbar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './topbar.html',
  styleUrl: './topbar.css'
})
export class TopbarComponent {
  @Output() toggleSidebar = new EventEmitter<void>();

  private readonly themeService = inject(ThemeService);
  readonly darkMode = this.themeService.darkMode;

  languages = [
    { label: 'English', code: 'EN', flag: '🇬🇧' },
    { label: 'Arabic', code: 'AR', flag: '🇲🇦' },
    { label: 'French', code: 'FR', flag: '🇫🇷' }
  ];
  currentLang = signal(this.languages[0]);
  showLangMenu = signal(false);

  toggleTheme() {
    this.themeService.toggleDarkMode(!this.darkMode());
  }

  selectLanguage(lang: any) {
    this.currentLang.set(lang);
    this.showLangMenu.set(false);
  }

  toggleLangMenu() {
    this.showLangMenu.update(v => !v);
  }
}