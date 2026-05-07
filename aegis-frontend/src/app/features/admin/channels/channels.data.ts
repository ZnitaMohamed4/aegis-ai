export type ChannelType = 'whatsapp' | 'telegram';
export type InstanceStatus = 'Connected' | 'Disconnected' | 'Pending QR Scan' | 'Unknown';

export interface EvolutionServerStatus {
  serverUrl: string;
  status: 'Online' | 'Offline';
  version: string;
  activeInstances: number;
  totalInstances: number;
  maxInstances: number;
  webhook: 'Connected' | 'Disconnected';
  warning: string;
}

export interface ChannelTab {
  key: ChannelType;
  label: string;
  comingSoon: boolean;
}

export interface ChildInfo {
  id: string;
  name: string;
  whatsappNumber: string;
}

export interface ChannelInstance {
  id: string;
  channelType: ChannelType;
  instanceName: string;
  ownerNumber: string;
  parentName: string;
  parentEmail: string;
  children: ChildInfo[];
  connectionType: 'Evolution API' | 'MTProto';
  status: InstanceStatus;
  lastActive: string;
  interceptedMessages: number;
}

export const CHANNEL_TABS: ChannelTab[] = [
  { key: 'whatsapp', label: 'WhatsApp (Evolution API)', comingSoon: false },
  { key: 'telegram', label: 'Telegram', comingSoon: true }
];
