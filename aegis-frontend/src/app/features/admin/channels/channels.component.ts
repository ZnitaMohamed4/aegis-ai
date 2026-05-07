import { CommonModule } from '@angular/common';
import { Component, computed, OnInit, signal, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PageHeaderComponent } from '@shared/index';
import { ApiService } from '@core/services/api.service';
import {
  CHANNEL_TABS,
  ChannelInstance,
  ChannelType,
  EvolutionServerStatus
} from './channels.data';

@Component({
  selector: 'app-channels',
  imports: [CommonModule, FormsModule, PageHeaderComponent],
  templateUrl: './channels.html',
  styleUrl: './channels.css',
})
export class ChannelsComponent implements OnInit {

  serverStatus = signal<EvolutionServerStatus>({
    serverUrl: 'Connecting...',
    status: 'Offline',
    version: 'Unknown',
    activeInstances: 0,
    totalInstances: 0,
    maxInstances: 5,
    webhook: 'Disconnected',
    warning: 'Checking connection...'
  });

  readonly channelTabs = CHANNEL_TABS;
  private apiService = inject(ApiService);

  activeTab = signal<ChannelType>('whatsapp');
  instances = signal<ChannelInstance[]>([]);
  isLoading = signal(true);

  /** Confirmation dialog for force-logout */
  confirmDeleteId = signal<string | null>(null);
  confirmDeleteName = signal('');

  filteredInstances = computed(() => {
    const active = this.activeTab();
    return this.instances().filter(instance => instance.channelType === active);
  });

  connectedCount = computed(() =>
    this.filteredInstances().filter(i => i.status === 'Connected').length
  );

  disconnectedCount = computed(() =>
    this.filteredInstances().filter(i => i.status === 'Disconnected').length
  );

  totalIntercepted = computed(() =>
    this.filteredInstances().reduce((sum, i) => sum + i.interceptedMessages, 0)
  );

  selectedTabMeta = computed(() => {
    const current = this.channelTabs.find(tab => tab.key === this.activeTab());
    return current ?? this.channelTabs[0];
  });

  ngOnInit() {
    this.loadChannels();
  }

  loadChannels() {
    this.isLoading.set(true);
    this.apiService.getAdminChannels().subscribe({
      next: (data) => {
        this.serverStatus.set(data.serverStatus);
        this.instances.set(data.instances);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Failed to load channels:', err);
        this.isLoading.set(false);
      }
    });
  }

  selectTab(tab: ChannelType) {
    this.activeTab.set(tab);
  }

  refreshData() {
    this.loadChannels();
  }

  /** Opens a confirmation dialog before force-deleting */
  promptDelete(instance: ChannelInstance) {
    this.confirmDeleteId.set(instance.id);
    this.confirmDeleteName.set(instance.instanceName);
  }

  cancelDelete() {
    this.confirmDeleteId.set(null);
    this.confirmDeleteName.set('');
  }

  confirmDelete() {
    const instanceId = this.confirmDeleteId();
    if (!instanceId) return;

    this.apiService.deleteAdminChannel(instanceId).subscribe({
      next: () => {
        this.instances.update(list => list.filter(i => i.id !== instanceId));
        this.cancelDelete();
      },
      error: (err) => {
        console.error('Failed to delete instance', err);
        this.cancelDelete();
      }
    });
  }

  getStatusDotClass(status: ChannelInstance['status']) {
    if (status === 'Connected') {
      return 'status-dot status-dot-connected';
    }
    if (status === 'Pending QR Scan') {
      return 'status-dot status-dot-pending';
    }
    return 'status-dot status-dot-disconnected';
  }

  formatNumber(num: string): string {
    if (!num || num.length < 5) return num || 'Unknown';
    return `+${num.slice(0, 3)} ${num.slice(3)}`;
  }
}
