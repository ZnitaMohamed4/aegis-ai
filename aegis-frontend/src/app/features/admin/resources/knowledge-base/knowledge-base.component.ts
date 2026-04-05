import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PageHeaderComponent } from '@shared/index';
import { TableModule } from 'primeng/table';
import { MOCK_INDEXED_DOCS, MOCK_RAG_METRICS, IndexedDocument } from '../resources.data';

@Component({
  selector: 'app-knowledge-base',
  standalone: true,
  imports: [CommonModule, FormsModule, PageHeaderComponent, TableModule],
  templateUrl: './knowledge-base.html',
  styleUrl: './knowledge-base.css',
})
export class KnowledgeBaseComponent {
  docs = signal<IndexedDocument[]>(MOCK_INDEXED_DOCS);
  metrics = signal(MOCK_RAG_METRICS);

  deleteDoc(id: string) {
    this.docs.update((current) => current.filter((d) => d.id !== id));
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
