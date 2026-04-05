import { CommonModule } from '@angular/common';
import { Component, computed, OnDestroy, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { PageHeaderComponent } from '@shared/index';
import {
  CHANNEL_INSTANCES,
  CHANNEL_TABS,
  ChannelInstance,
  ChannelType,
  EVOLUTION_SERVER_STATUS
} from './channels.data';

@Component({
  selector: 'app-channels',
  imports: [CommonModule, FormsModule, DrawerModule, PageHeaderComponent],
  templateUrl: './channels.html',
  styleUrl: './channels.css',
})
export class ChannelsComponent implements OnDestroy {

  readonly serverStatus = EVOLUTION_SERVER_STATUS;
  readonly channelTabs = CHANNEL_TABS;

  activeTab = signal<ChannelType>('whatsapp-baileys');
  instances = signal<ChannelInstance[]>([...CHANNEL_INSTANCES]);

  drawerVisible = signal(false);
  wizardStep = signal<1 | 2 | 3>(1);
  countdownSeconds = signal(60);

  instanceName = signal('');
  childIdentifier = signal('');
  phoneNumber = signal('');
  formError = signal('');

  private countdownHandle?: ReturnType<typeof setInterval>;

  filteredInstances = computed(() => {
    const active = this.activeTab();
    return this.instances().filter(instance => instance.channelType === active);
  });

  qrProgress = computed(() => `${Math.round((this.countdownSeconds() / 60) * 100)}%`);

  selectedTabMeta = computed(() => {
    const current = this.channelTabs.find(tab => tab.key === this.activeTab());
    return current ?? this.channelTabs[0];
  });

  ngOnDestroy() {
    this.stopCountdown();
  }

  selectTab(tab: ChannelType) {
    this.activeTab.set(tab);
  }

  openConnectDrawer() {
    this.drawerVisible.set(true);
    this.wizardStep.set(1);
    this.formError.set('');
    this.stopCountdown();
    this.countdownSeconds.set(60);
  }

  closeDrawer() {
    this.drawerVisible.set(false);
    this.stopCountdown();
  }

  nextStepFromForm() {
    if (!this.instanceName().trim() || !this.childIdentifier().trim() || !this.phoneNumber().trim()) {
      this.formError.set('Please fill in all fields before continuing.');
      return;
    }

    this.formError.set('');
    this.wizardStep.set(2);
    this.startCountdown();
  }

  completeScan() {
    this.stopCountdown();

    const name = this.instanceName().trim();
    const childIdentifier = this.childIdentifier().trim();
    const phoneNumber = this.phoneNumber().trim();
    const id = `inst-${Date.now()}`;

    this.instances.update(existing => [
      {
        id,
        channelType: 'whatsapp-baileys',
        instanceName: name,
        childIdentifier,
        phoneNumber,
        connectionType: 'Baileys',
        status: 'Connected',
        lastActive: 'Just now',
        interceptedMessages: 0
      },
      ...existing
    ]);

    this.wizardStep.set(3);
  }

  finishWizard() {
    this.closeDrawer();
    this.instanceName.set('');
    this.childIdentifier.set('');
    this.phoneNumber.set('');
    this.wizardStep.set(1);
    this.countdownSeconds.set(60);
  }

  refreshQr() {
    this.countdownSeconds.set(60);
    this.startCountdown();
  }

  reconnectInstance(instanceId: string) {
    this.instances.update(list =>
      list.map(instance =>
        instance.id === instanceId
          ? { ...instance, status: 'Connected', lastActive: 'Just now' }
          : instance
      )
    );
  }

  disconnectInstance(instanceId: string) {
    this.instances.update(list =>
      list.map(instance =>
        instance.id === instanceId
          ? { ...instance, status: 'Disconnected', lastActive: 'Just now' }
          : instance
      )
    );
  }

  deleteInstance(instanceId: string) {
    this.instances.update(list => list.filter(instance => instance.id !== instanceId));
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

  private startCountdown() {
    this.stopCountdown();

    this.countdownHandle = setInterval(() => {
      const current = this.countdownSeconds();
      if (current <= 1) {
        this.countdownSeconds.set(0);
        this.stopCountdown();
        return;
      }

      this.countdownSeconds.set(current - 1);
    }, 1000);
  }

  private stopCountdown() {
    if (this.countdownHandle) {
      clearInterval(this.countdownHandle);
      this.countdownHandle = undefined;
    }
  }
}
