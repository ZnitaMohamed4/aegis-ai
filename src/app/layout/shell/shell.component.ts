import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { TopbarComponent } from '../topbar/topbar.component';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { ChatbotWidgetComponent } from '../../features/chatbot/chatbot-widget/chatbot-widget.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, TopbarComponent, SidebarComponent, ChatbotWidgetComponent],
  templateUrl: './shell.html',
  styleUrl: './shell.css'
})
export class ShellComponent {
  sidebarCollapsed = false;

  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
    // Trigger resize after sidebar transition so charts recalculate
    setTimeout(() => window.dispatchEvent(new Event('resize')), 320);
  }
}