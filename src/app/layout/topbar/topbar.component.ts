import { Component, EventEmitter, inject, Output } from '@angular/core';
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

  toggleTheme() {
    this.themeService.toggleDarkMode(!this.darkMode());
  }
}