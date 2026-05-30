import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PageHeaderComponent } from '@shared/index';
import { TableModule } from 'primeng/table';
import { MOCK_RAG_METRICS, IndexedDocument } from '../resources.data';
import { ApiService } from '../../../../core/services/api.service';

@Component({
  selector: 'app-knowledge-base',
  standalone: true,
  imports: [CommonModule, FormsModule, PageHeaderComponent, TableModule],
  templateUrl: './knowledge-base.html',
  styleUrl: './knowledge-base.css',
})
export class KnowledgeBaseComponent {
  docs = signal<IndexedDocument[]>([]);
  metrics = signal(MOCK_RAG_METRICS);

  constructor(private apiService: ApiService) {}

  ngOnInit() {
    this.loadData();
  }

  loadData() {
    this.apiService.getKnowledgeDocuments().subscribe({
      next: (docs) => {
        // Parse dates
        this.docs.set(docs.map(d => ({...d, dateAdded: new Date(d.dateAdded)})));
      },
      error: (err) => console.error('Failed to load docs', err)
    });

    this.apiService.getKnowledgeStats().subscribe({
      next: (stats) => {
        this.metrics.set({
          ...stats,
          lastUpdate: new Date(stats.lastUpdate || new Date())
        });
      },
      error: (err) => console.error('Failed to load stats', err)
    });
  }

  deleteDoc(id: string) {
    this.apiService.deleteKnowledgeDocument(id).subscribe({
      next: () => {
        this.docs.update((current) => current.filter((d) => d.id !== id));
      },
      error: (err) => console.error('Failed to delete doc', err)
    });
  }

  // Helper formatting methods
  formatDate(date: Date) {
    return date.toLocaleDateString();
  }

  formatSize(bytes: number) {
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
