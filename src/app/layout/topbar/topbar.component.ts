import { Component, computed, EventEmitter, inject, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, NavigationEnd } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs/operators';
import { ThemeService } from '@core/services/theme.service';
import { AuthService } from '@core/services/auth.service';

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
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  readonly darkMode = this.themeService.darkMode;

  /**
   * We convert router events to a signal to trigger reactivity in our computed signals.
   */
  private navEvents = toSignal(
    this.router.events.pipe(filter(event => event instanceof NavigationEnd))
  );

  isParentView = computed(() => {
    this.navEvents(); // Register as dependency
    return this.router.url.startsWith('/parent');
  });

  logout() {
    this.authService.logout();
  }

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