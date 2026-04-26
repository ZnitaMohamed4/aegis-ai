import { Component, computed, inject, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive, NavigationEnd } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs/operators';


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
  collapsed = input<boolean>(false);
  
  private router = inject(Router);

  /**
   * We convert router events to a signal to trigger reactivity in our computed signals.
   * This ensures isParentView updates automatically on every NavigationEnd.
   */
  private navEvents = toSignal(
    this.router.events.pipe(filter(event => event instanceof NavigationEnd))
  );

  isParentView = computed(() => {
    // Accessing navEvents() registers this computed as a dependent of router navigation
    this.navEvents(); 
    return this.router.url.startsWith('/parent');
  });

  parentNav: NavGroup[] = [
    {
      title: 'Overview',
      items: [
        { label: 'Dashboard', icon: 'pi-home', route: '/parent/dashboard' },
      ]
    },
    {
      title: 'Surveillance',
      items: [
        { label: 'Live Alerts', icon: 'pi-bell', route: '/parent/alerts', dot: 'pulse' },
        { label: 'Risk Profile', icon: 'pi-chart-line', route: '/parent/risk-profile' },
      ]
    },
    {
      title: 'Management',
      items: [
        { label: 'Reports', icon: 'pi-file', route: '/parent/reports' },
      ]
    },
    {
      title: 'Configuration',
      items: [
        { label: 'WhatsApp Setup', icon: 'pi-whatsapp', route: '/parent/whatsapp-setup' },
        { label: 'Settings', icon: 'pi-sliders-h', route: '/parent/settings' },
      ]
    },
    {
      title: 'Education',
      items: [
        { label: 'Chatbot', icon: 'pi-graduation-cap', route: '/parent/chatbot' },
      ]
    }
  ];

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
        { label: 'Message Intel', icon: 'pi-shield', route: '/admin/conversations' },
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