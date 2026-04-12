import { Routes } from '@angular/router';
import { authGuard, adminGuard, parentGuard } from '@core/guards/auth.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full'
  },
  {
    path: 'login',
    loadComponent: () => import('@features/auth/login/login.component').then(c => c.LoginComponent)
  },

  // Admin shell
  {
    path: 'admin',
    canActivate: [authGuard, adminGuard],
    loadComponent: () =>
      import('@layout/shell/shell.component').then(c => c.ShellComponent),
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      { path: 'dashboard', loadComponent: () => import('@features/admin/dashboard/dashboard.component').then(c => c.DashboardComponent) },
      { path: 'alerts', loadComponent: () => import('@features/admin/alerts/alerts.component').then(c => c.AlertsComponent) },
      { path: 'review-queue', loadComponent: () => import('@features/admin/review-queue/review-queue.component').then(c => c.ReviewQueueComponent) },
      { path: 'conversations', loadComponent: () => import('@features/admin/conversations/conversations.component').then(c => c.ConversationsComponent) },
      { path: 'risk-profiles', loadComponent: () => import('@features/admin/risk-profiles/risk-profiles.component').then(c => c.RiskProfilesComponent) },
      { path: 'users', loadComponent: () => import('@features/admin/users/users.component').then(c => c.UsersComponent) },
      { path: 'reports', loadComponent: () => import('@features/admin/reports/reports.component').then(c => c.ReportsComponent) },
      { path: 'ai-config', loadComponent: () => import('@features/admin/ai-config/ai-config.component').then(c => c.AiConfigComponent) },
      { path: 'resources', loadChildren: () => import('@features/admin/resources/resources.routes').then(m => m.RESOURCES_ROUTES) },
      { path: 'channels', loadComponent: () => import('@features/admin/channels/channels.component').then(c => c.ChannelsComponent) },
      { path: 'settings', loadComponent: () => import('@features/admin/settings/settings.component').then(c => c.SettingsComponent) },
      { path: 'analytics', loadComponent: () => import('@features/admin/analytics/analytics.component').then(c => c.AnalyticsComponent) },
      { path: 'chatbot', loadComponent: () => import('@features/chatbot/chatbot-page/chatbot-page.component').then(c => c.ChatbotPageComponent) },
    ]
  },

  // Parent shell
  {
    path: 'parent',
    canActivate: [authGuard, parentGuard],
    loadComponent: () =>
      import('@layout/shell/shell.component').then(c => c.ShellComponent),
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      { path: 'dashboard', loadComponent: () => import('@features/parent/dashboard/dashboard.component').then(c => c.DashboardComponent) },
      { path: 'alerts', loadComponent: () => import('@features/parent/alerts/alerts.component').then(c => c.AlertsComponent) },
      { path: 'conversations', loadComponent: () => import('@features/parent/conversations/conversations.component').then(c => c.ConversationsComponent) },
      { path: 'reports', loadComponent: () => import('@features/parent/reports/reports.component').then(c => c.ReportsComponent) },
      { path: 'risk-profile', loadComponent: () => import('@features/parent/risk-profile/risk-profile.component').then(c => c.RiskProfileComponent) },
      { path: 'whatsapp-setup', loadComponent: () => import('@features/parent/whatsapp-setup/whatsapp-setup.component').then(c => c.WhatsappSetupComponent) },
      { path: 'settings', loadComponent: () => import('@features/parent/settings/settings.component').then(c => c.SettingsComponent) },
      { path: 'chatbot', loadComponent: () => import('@features/chatbot/chatbot-page/chatbot-page.component').then(c => c.ChatbotPageComponent) },
    ]
  },

  { path: '**', redirectTo: 'login' }
];