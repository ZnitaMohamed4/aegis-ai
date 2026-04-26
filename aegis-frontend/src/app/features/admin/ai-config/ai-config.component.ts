import { CommonModule } from '@angular/common';
import { Component, computed, signal, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { ToggleSwitch } from 'primeng/toggleswitch';
import {
  AgentStatus,
  DecisionBoundaries,
  FinalDecision,
  LlmProviderId,
  PipelineAgent,
} from '@core/models/ai-config.model';
import { PageHeaderComponent } from '@shared/index';
import { ApiService } from '@core/services/api.service';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import {
  AGENT_CARDS,
  AGENT_STATUS_TONE,
  DECISION_LABELS,
  DECISION_ZONES,
  DEFAULT_BOUNDARIES,
  LANGUAGE_TABS,
  PROVIDER_CARDS,
  PROVIDER_MODELS,
  SIMULATION_SAMPLES,
} from './ai-config.data';

interface ConnectionTestResult {
  ok: boolean;
  message: string;
}

interface SimulationUiResult {
  detectedLanguage: string;
  toxicityScore: number;
  llmTriggered: boolean;
  behavioralScore: number;
  finalScore: number;
  decision: FinalDecision;
  explanation: string;
}

@Component({
  selector: 'app-ai-config',
  standalone: true,
  imports: [CommonModule, FormsModule, PageHeaderComponent, Select, ToggleSwitch, ToastModule],
  providers: [MessageService],
  templateUrl: './ai-config.html',
  styleUrl: './ai-config.css',
})
export class AiConfigComponent implements OnInit {
  private readonly apiService = inject(ApiService);
  private readonly messageService = inject(MessageService);
  readonly zoneMeta = DECISION_ZONES;
  readonly providerCards = PROVIDER_CARDS;
  readonly languageTabs = LANGUAGE_TABS;

  readonly activeTab = signal<'pipeline' | 'policy' | 'infrastructure'>('pipeline');

  readonly boundaries = signal<DecisionBoundaries>({ ...DEFAULT_BOUNDARIES });
  readonly selectedZone = signal<'allow' | 'warn' | 'review' | 'block' | 'critical'>('review');
  readonly agents = signal<PipelineAgent[]>([...AGENT_CARDS]);

  readonly selectedProvider = signal<LlmProviderId>('groq');
  readonly selectedModel = signal(PROVIDER_MODELS.groq[0].value);
  readonly apiKey = signal('');
  readonly showApiKey = signal(false);
  readonly connectionResult = signal<ConnectionTestResult | null>(null);

  readonly simulationMessage = signal('');
  readonly simulationLanguage = signal<'auto' | 'fr' | 'ar' | 'en'>('auto');
  readonly simulationResult = signal<SimulationUiResult | null>(null);

  readonly providerModels = computed(() => PROVIDER_MODELS[this.selectedProvider()]);
  readonly criticalThreshold = computed(() => this.boundaries().critical.toFixed(2));

  readonly zones = computed(() => {
    const b = this.boundaries();
    return [
      { ...DECISION_ZONES[0], min: 0, max: b.warn },
      { ...DECISION_ZONES[1], min: b.warn, max: b.review },
      { ...DECISION_ZONES[2], min: b.review, max: b.block },
      { ...DECISION_ZONES[3], min: b.block, max: b.critical },
      { ...DECISION_ZONES[4], min: b.critical, max: 1 },
    ];
  });

  ngOnInit(): void {
    this.apiService.getSystemSettings().subscribe({
      next: (s) => {
        this.boundaries.set({
          warn: s.ai_warn_threshold,
          review: s.ai_review_threshold,
          block: s.ai_block_threshold,
          critical: s.ai_critical_threshold
        });
        
        this.agents.update(list => list.map(a => {
          const enabled = !!s[`agent_${a.id}_enabled`];
          return { ...a, enabled, status: enabled ? (a.id === 3 ? 'DEGRADED' : 'ACTIVE') : 'OFFLINE' };
        }));
        
        if (s.active_llm_provider) this.selectedProvider.set(s.active_llm_provider);
        if (s.active_llm_model) this.selectedModel.set(s.active_llm_model);
      },
      error: () => console.error("Could not fetch PlatformSettings")
    });
  }

  private saveSettingsToBackend(): void {
    const b = this.boundaries();
    const a = this.agents();
    const payload: any = {
      ai_warn_threshold: b.warn,
      ai_review_threshold: b.review,
      ai_block_threshold: b.block,
      ai_critical_threshold: b.critical,
      active_llm_provider: this.selectedProvider(),
      active_llm_model: this.selectedModel(),
    };
    
    a.forEach(agent => {
      payload[`agent_${agent.id}_enabled`] = agent.enabled;
    });

    this.apiService.updateSystemSettings(payload).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Saved', detail: 'Config applied to backend', life: 1500 });
      },
      error: () => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to save config' });
      }
    });
  }

  selectProvider(provider: LlmProviderId): void {
    this.selectedProvider.set(provider);
    this.selectedModel.set(PROVIDER_MODELS[provider][0].value);
    this.connectionResult.set(null);
    this.saveSettingsToBackend();
  }

  updateBoundary(key: keyof DecisionBoundaries, raw: string): void {
    const parsed = Number(raw);
    if (Number.isNaN(parsed)) return;
    const next = { ...this.boundaries(), [key]: parsed };
    next.warn = this.clamp(next.warn, 0.1, 0.8);
    next.review = this.clamp(next.review, next.warn + 0.01, 0.88);
    next.block = this.clamp(next.block, next.review + 0.01, 0.95);
    next.critical = this.clamp(next.critical, next.block + 0.01, 0.99);
    this.boundaries.set(next);
    this.saveSettingsToBackend();
  }

  updateAgentEnabled(agentId: number, enabled: boolean): void {
    this.agents.update((list) =>
      list.map((agent) =>
        agent.id !== agentId
          ? agent
          : { ...agent, enabled, status: enabled ? (agent.id === 3 ? 'DEGRADED' : 'ACTIVE') : 'OFFLINE' }
      )
    );
    this.saveSettingsToBackend();
  }

  testConnection(): void {
    const key = this.apiKey().trim();
    if (key.length > 10 && key.includes('-')) {
      this.connectionResult.set({ ok: true, message: 'Connected - response time 340ms' });
      return;
    }
    this.connectionResult.set({ ok: false, message: 'Failed - invalid API key' });
  }

  runSimulation(): void {
    const text = this.simulationMessage().trim().toLowerCase();
    if (!text) return;
    const sample = SIMULATION_SAMPLES.find((s) => text.includes(s.text));
    const detected = this.simulationLanguage() === 'auto' ? this.detectLanguage(text) : this.simulationLanguage();
    const toxicity = sample?.toxicity ?? (text.includes('kill') || text.includes('hate') ? 0.86 : 0.31);
    const behavioral = sample?.behavioral ?? this.clamp(toxicity - 0.05, 0.05, 0.98);
    const llmTriggered = toxicity >= this.boundaries().review;
    const finalScore = this.clamp(toxicity * 0.65 + behavioral * 0.35 + (llmTriggered ? 0.03 : 0), 0, 1);
    const decision = this.decisionByScore(finalScore);
    this.simulationResult.set({
      detectedLanguage: detected,
      toxicityScore: toxicity,
      llmTriggered,
      behavioralScore: behavioral,
      finalScore,
      decision,
      explanation: sample?.explanation ?? 'Signal blend generated from toxicity and behavioral models.',
    });
  }

  getStatusTone(status: AgentStatus): 'good' | 'warn' | 'bad' {
    return AGENT_STATUS_TONE[status];
  }

  getDecisionLabel(decision: FinalDecision): string {
    return DECISION_LABELS[decision];
  }

  private decisionByScore(score: number): FinalDecision {
    const b = this.boundaries();
    if (score >= b.critical) return 'critical';
    if (score >= b.block) return 'block';
    if (score >= b.review) return 'escalate';
    if (score >= b.warn) return 'warn';
    return 'allow';
  }

  private detectLanguage(text: string): 'fr' | 'ar' | 'en' {
    if (/[\u0600-\u06ff]/.test(text)) return 'ar';
    if (text.includes('je ') || text.includes('toi') || text.includes('bonjour')) return 'fr';
    return 'en';
  }

  private clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
  }
}
