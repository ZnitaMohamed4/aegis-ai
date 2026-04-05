import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PageHeaderComponent } from '@shared/index';
import { SelectModule } from 'primeng/select';
import { DOCUMENT_CATEGORIES, UploadTask } from '../resources.data';

@Component({
  selector: 'app-import',
  standalone: true,
  imports: [CommonModule, FormsModule, PageHeaderComponent, SelectModule],
  templateUrl: './import.html',
  styleUrl: './import.css',
})
export class ImportComponent {
  categories = DOCUMENT_CATEGORIES;

  selectedLang = signal<'fr' | 'ar' | 'en'>('fr');
  selectedCategory = signal<string>(this.categories[0].value);

  isDragging = signal(false);
  activeUploads = signal<UploadTask[]>([]);

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(false);

    if (event.dataTransfer?.files) {
      this.handleFiles(event.dataTransfer.files);
    }
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.handleFiles(input.files);
    }
    input.value = ''; // Reset
  }

  private handleFiles(files: FileList) {
    const newUploads: UploadTask[] = Array.from(files).map((file) => ({
      id: Math.random().toString(36).substring(7),
      file,
      progress: 0,
      status: 'uploading',
      language: this.selectedLang(),
      category: this.selectedCategory(),
    }));

    this.activeUploads.update((u) => [...newUploads, ...u].slice(0, 10)); // Keep top 10 recent

    // Simulate processing pipeline
    newUploads.forEach((task) => this.simulatePipeline(task));
  }

  private simulatePipeline(task: UploadTask) {
    const updateTask = (updates: Partial<UploadTask>) => {
      this.activeUploads.update((uploads) =>
        uploads.map((u) => (u.id === task.id ? { ...u, ...updates } : u)),
      );
    };

    // Very fast simulation of the pipeline
    setTimeout(() => {
      updateTask({ progress: 20, status: 'extracting' });
    }, 800);
    setTimeout(() => {
      updateTask({ progress: 45, status: 'chunking' });
    }, 1600);
    setTimeout(() => {
      updateTask({ progress: 80, status: 'embedding' });
    }, 2800);
    setTimeout(() => {
      updateTask({ progress: 100, status: 'indexing' });
    }, 4000);
    setTimeout(() => {
      updateTask({ status: 'completed' });
    }, 4500);
  }

  formatSize(bytes: number) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
