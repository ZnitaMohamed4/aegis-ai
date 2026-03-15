import { Routes } from '@angular/router';

export const RESOURCES_ROUTES: Routes = [
  { path: '', redirectTo: 'import', pathMatch: 'full' },
  {
    path: 'import',
    loadComponent: () => import('./import/import.component').then((c) => c.ImportComponent),
  },
  {
    path: 'knowledge-base',
    loadComponent: () =>
      import('./knowledge-base/knowledge-base.component').then((c) => c.KnowledgeBaseComponent),
  },
];
