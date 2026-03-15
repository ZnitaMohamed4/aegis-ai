import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  dot?: 'pulse' | 'static';
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css'
})
export class SidebarComponent {
  @Input() collapsed = false;

  adminNav: NavGroup[] = [
    {
      title: 'Overview',
      items: [
        { label: 'Dashboard', icon: 'pi-home', route: '/admin/dashboard' },
      ]
    },
    {
      title: 'Surveillance',
      items: [
        { label: 'Live Alerts', icon: 'pi-bell', route: '/admin/alerts', dot: 'pulse' },
        { label: 'Review Queue', icon: 'pi-clock', route: '/admin/review-queue', dot: 'static' },
        { label: 'Conversations', icon: 'pi-comments', route: '/admin/conversations' },
        { label: 'Risk Profiles', icon: 'pi-user-minus', route: '/admin/risk-profiles' },
      ]
    },
    {
      title: 'Management',
      items: [
        { label: 'Users', icon: 'pi-users', route: '/admin/users' },
        { label: 'Reports', icon: 'pi-file', route: '/admin/reports' },
      ]
    },
    {
      title: 'Configuration',
      items: [
        { label: 'AI Config', icon: 'pi-cog', route: '/admin/ai-config' },
        { label: 'Channels', icon: 'pi-mobile', route: '/admin/channels' },
        { label: 'Settings', icon: 'pi-sliders-h', route: '/admin/settings' },
      ]
    },
    {
      title: 'Knowledge Base',
      items: [
        { label: 'Document Import', icon: 'pi-cloud-upload', route: '/admin/resources/import' },
        { label: 'Vector Store', icon: 'pi-database', route: '/admin/resources/knowledge-base' },
      ]
    },
    {
      title: 'Analytics',
      items: [
        { label: 'Analytics', icon: 'pi-chart-bar', route: '/admin/analytics' },
      ]
    },
    {
      title: 'Education',
      items: [
        { label: 'Chatbot', icon: 'pi-graduation-cap', route: '/admin/chatbot' },
      ]
    }
  ];
}