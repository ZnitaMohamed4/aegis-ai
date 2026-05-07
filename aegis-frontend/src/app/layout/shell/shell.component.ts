import { Component, inject } from '@angular/core';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { TopbarComponent } from '../topbar/topbar.component';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { ChatbotWidgetComponent } from '../../features/chatbot/chatbot-widget/chatbot-widget.component';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, TopbarComponent, SidebarComponent, ChatbotWidgetComponent],
  templateUrl: './shell.html',
  styleUrl: './shell.css'
})
export class ShellComponent {
  sidebarCollapsed = true;   // Always start collapsed
  sidebarHovered = false;    // Tracks mouse hover on sidebar
  mobileSidebarOpen = false;
  isMobile = window.innerWidth <= 640;

  private router = inject(Router);

  constructor() {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe(() => {
      // Auto-collapse on mobile when navigating
      if (this.mobileSidebarOpen) {
        this.mobileSidebarOpen = false;
      }
    });

    window.addEventListener('resize', () => {
      this.isMobile = window.innerWidth <= 640;
      if (!this.isMobile && this.mobileSidebarOpen) {
        this.mobileSidebarOpen = false;
      }
    });
  }

  /** Sidebar is visually collapsed only when not hovered */
  get effectiveCollapsed(): boolean {
    return this.sidebarCollapsed && !this.sidebarHovered;
  }

  onSidebarEnter() {
    if (!this.isMobile) {
      this.sidebarHovered = true;
    }
  }

  onSidebarLeave() {
    if (!this.isMobile) {
      this.sidebarHovered = false;
    }
  }

  toggleSidebar() {
    if (window.innerWidth <= 640) {
      this.mobileSidebarOpen = !this.mobileSidebarOpen;
    } else {
      // On desktop: toggle pins the sidebar open/closed
      this.sidebarCollapsed = !this.sidebarCollapsed;
      this.sidebarHovered = false;
    }
    // Trigger resize after sidebar transition so charts recalculate
    setTimeout(() => window.dispatchEvent(new Event('resize')), 320);
  }
}