export type ChannelType = 'whatsapp-baileys' | 'whatsapp-cloud' | 'instagram' | 'messenger';
export type InstanceStatus = 'Connected' | 'Disconnected' | 'Pending QR Scan';

export interface EvolutionServerStatus {
  serverUrl: string;
  status: 'Online' | 'Offline';
  version: string;
  activeInstances: number;
  maxInstances: number;
  webhook: 'Connected' | 'Disconnected';
  warning: string;
}

export interface ChannelTab {
  key: ChannelType;
  label: string;
  comingSoon: boolean;
}

export interface ChannelInstance {
  id: string;
  channelType: ChannelType;
  instanceName: string;
  childIdentifier: string;
  phoneNumber: string;
  connectionType: 'Baileys' | 'Cloud API';
  status: InstanceStatus;
  lastActive: string;
  interceptedMessages: number;
}

export const EVOLUTION_SERVER_STATUS: EvolutionServerStatus = {
  serverUrl: 'http://localhost:8080',
  status: 'Online',
  version: 'v2.3.7',
  activeInstances: 3,
  maxInstances: 5,
  webhook: 'Connected',
  warning: 'Uses WhatsApp Web protocol (Baileys). For academic/prototype use only.'
};

export const CHANNEL_TABS: ChannelTab[] = [
  { key: 'whatsapp-baileys', label: 'WhatsApp Baileys', comingSoon: false },
  { key: 'whatsapp-cloud', label: 'WhatsApp Cloud API', comingSoon: true },
  { key: 'instagram', label: 'Instagram', comingSoon: true },
  { key: 'messenger', label: 'Messenger', comingSoon: true }
];

export const CHANNEL_INSTANCES: ChannelInstance[] = [
  {
    id: 'inst-a1',
    channelType: 'whatsapp-baileys',
    instanceName: 'child-a1-baileys',
    childIdentifier: 'Child #A1',
    phoneNumber: '+212 6XX XXX X01',
    connectionType: 'Baileys',
    status: 'Connected',
    lastActive: '2 min ago',
    interceptedMessages: 142
  },
  {
    id: 'inst-b2',
    channelType: 'whatsapp-baileys',
    instanceName: 'child-b2-baileys',
    childIdentifier: 'Child #B2',
    phoneNumber: '+212 6XX XXX X02',
    connectionType: 'Baileys',
    status: 'Connected',
    lastActive: '1 hr ago',
    interceptedMessages: 98
  },
  {
    id: 'inst-c3',
    channelType: 'whatsapp-baileys',
    instanceName: 'child-c3-baileys',
    childIdentifier: 'Child #C3',
    phoneNumber: '+212 6XX XXX X03',
    connectionType: 'Baileys',
    status: 'Disconnected',
    lastActive: '3 days ago',
    interceptedMessages: 45
  }
];
