import { CommonModule } from '@angular/common';
import { Component, computed, signal, OnInit, OnDestroy, inject } from '@angular/core';
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
  BN_OBSERVABLES,
  BN_PATHWAYS,
  BN_EDGES,
  BN_PATHWAY_COLORS,
  BnObservableDef,
  BnPathwayDef,
} from './ai-config.data';

interface BnObservableNode {
  id: string;
  label: string;
  state: string;
  states: string[];
  priors: Record<string, number>;
  pathway: string[];
  animPhase: 'idle' | 'active' | 'settled';
}

interface BnPathwayNode {
  id: string;
  label: string;
  color: string;
  probs: Record<string, number>;
  highProb: number;
  animPhase: 'idle' | 'computing' | 'settled';
}

interface BnOverallNode {
  probs: Record<string, number>;
  riskScore: number;
  riskLevel: string;
  archetype: string;
  animPhase: 'idle' | 'computing' | 'settled';
}

interface ContactOption {
  jid: string;
  label: string;
}

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
  agentLatencies: {
    agent_1_2: number;
    agent_3: number;
    agent_4: number;
    agent_5: number;
  };
  needsAudit: boolean;
  escalationRisk: number;
  mlCorrected: boolean;
  category?: string;
  isDarija: boolean;
  darijaScript?: 'arabizi' | 'arabic' | null;
}

interface PipelineNodeState {
  id: string;
  name: string;
  icon: string;
  role: string;
  state: 'idle' | 'pending' | 'active' | 'completed' | 'skipped';
  latency: number | null;
  detail: string;
}

interface GraphNode {
  id: string;
  cx: number;
  cy: number;
  icon: string;
  name: string;
  role: string;
  agentNum: string;
}

// SVG Graph Layout — LangGraph architecture as a directed graph
const GRAPH_NODES: GraphNode[] = [
  { id: '1', cx: 320, cy: 120, agentNum: '1', name: 'Router',   role: 'Classifier',  icon: 'pi pi-sitemap' },
  { id: '2', cx: 490, cy: 240, agentNum: '2', name: 'Auditor',  role: 'LLM Review',  icon: 'pi pi-eye' },
  { id: '3', cx: 320, cy: 360, agentNum: '3', name: 'Profiler', role: 'Behavioral',  icon: 'pi pi-chart-bar' },
  { id: '4', cx: 320, cy: 480, agentNum: '4', name: 'Enforcer', role: 'Decision',    icon: 'pi pi-shield' },
];

const GRAPH_PATHS = {
  startToPipeline: 'M 450,100 L 450,155',
  pipelineToAuditor: 'M 465,165 C 520,170 620,195 690,215',
  auditorToProfiler: 'M 690,265 C 620,290 520,340 465,360',
  pipelineToFast: 'M 435,165 C 390,230 395,310 440,360',
  profilerToEnforcer: 'M 450,420 L 450,475',
};


@Component({
  selector: 'app-ai-config',
  standalone: true,
  imports: [CommonModule, FormsModule, PageHeaderComponent, Select, ToggleSwitch, ToastModule],
  providers: [MessageService],
  templateUrl: './ai-config.html',
  styleUrl: './ai-config.css',
})
export class AiConfigComponent implements OnInit, OnDestroy {
  private readonly apiService = inject(ApiService);
  private readonly messageService = inject(MessageService);
  readonly zoneMeta = DECISION_ZONES;
  readonly providerCards = PROVIDER_CARDS;
  readonly languageTabs = LANGUAGE_TABS;
  readonly BN_OBSERVABLES = BN_OBSERVABLES;
  readonly BN_PATHWAYS = BN_PATHWAYS;

  readonly activeTab = signal<'pipeline' | 'policy' | 'infrastructure' | 'simulator' | 'bn-brain'>('pipeline');

  readonly boundaries = signal<DecisionBoundaries>({ ...DEFAULT_BOUNDARIES });
  readonly selectedZone = signal<'allow' | 'warn' | 'review' | 'block' | 'critical'>('review');
  readonly agents = signal<PipelineAgent[]>([...AGENT_CARDS]);

  readonly selectedProvider = signal<LlmProviderId>('groq');
  readonly selectedModel = signal(PROVIDER_MODELS.groq[0].value);
  readonly apiKey = signal('');
  readonly showApiKey = signal(false);
  readonly connectionResult = signal<ConnectionTestResult | null>(null);

  readonly simulationMessage = signal('');
  readonly simulationLanguage = signal<'auto' | 'fr' | 'ar' | 'en' | 'darija'>('auto');
  readonly simulationResult = signal<SimulationUiResult | null>(null);
  readonly isSimulating = signal(false);
  readonly graphNodes = signal<GraphNode[]>(GRAPH_NODES);
  readonly activePath = signal<'none' | 'fast' | 'audit'>('none');
  readonly activePathSegments = signal<string[]>([]);
  readonly packetKey = signal(0);
  readonly pipelineNodes = signal<PipelineNodeState[]>([
    { id: 'agent12', name: 'Gatekeeper + Classifier', icon: 'pi-shield', role: 'Pattern detection & ML scoring', state: 'idle', latency: null, detail: '' },
    { id: 'agent3', name: 'Semantic Auditor', icon: 'pi-eye', role: 'LLM context review', state: 'idle', latency: null, detail: '' },
    { id: 'agent4', name: 'Behavioral Profiler', icon: 'pi-chart-bar', role: 'Bayesian risk model', state: 'idle', latency: null, detail: '' },
    { id: 'agent5', name: 'Decision Enforcer', icon: 'pi-lock', role: 'Final policy & actions', state: 'idle', latency: null, detail: '' },
  ]);
  private animationTimers: ReturnType<typeof setTimeout>[] = [];

  // ═══ BN Brain Map signals ═══
  readonly bnObservables = signal<BnObservableNode[]>([]);
  readonly bnPathwayNodes = signal<BnPathwayNode[]>([]);
  readonly bnOverall = signal<BnOverallNode>({ probs: {}, riskScore: 0, riskLevel: 'LOW', archetype: 'Normal User', animPhase: 'idle' });
  readonly bnIsRunning = signal(false);
  readonly bnHasResult = signal(false);
  readonly bnContacts = signal<ContactOption[]>([]);
  readonly bnSelectedContact = signal<string>('');
  readonly bnCustomMode = signal(false);
  readonly bnCustomEvidence = signal<Record<string, string>>({});
  readonly bnError = signal<string | null>(null);

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

    // Load live agent latencies from Redis
    this.apiService.getAgentLatencies().subscribe({
      next: (lat) => {
        this.agents.update(list => list.map(a => ({
          ...a,
          latencyMs: lat[`agent_${a.id}`] ?? a.latencyMs
        })));
      }
    });
  }

  ngOnDestroy(): void {
    this.animationTimers.forEach(t => clearTimeout(t));
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
    this.connectionResult.set(null);
    this.apiService.testLlmConnection().subscribe({
      next: (res) => this.connectionResult.set({ ok: res.ok, message: res.message }),
      error: () => this.connectionResult.set({ ok: false, message: 'Network error — backend unreachable' })
    });
  }

  runSimulation(): void {
    const text = this.simulationMessage().trim();
    if (!text) return;
    
    // Clear any existing animation timers
    this.animationTimers.forEach(t => clearTimeout(t));
    this.animationTimers = [];
    
    // Reset result and start animation
    this.simulationResult.set(null);
    this.isSimulating.set(true);
    
    // Show all nodes as pending
    this.pipelineNodes.set([
      { id: 'agent12', name: 'Gatekeeper + Classifier', icon: 'pi-shield', role: 'Pattern detection & ML scoring', state: 'pending', latency: null, detail: '' },
      { id: 'agent3', name: 'Semantic Auditor', icon: 'pi-eye', role: 'LLM context review', state: 'pending', latency: null, detail: '' },
      { id: 'agent4', name: 'Behavioral Profiler', icon: 'pi-chart-bar', role: 'Bayesian risk model', state: 'pending', latency: null, detail: '' },
      { id: 'agent5', name: 'Decision Enforcer', icon: 'pi-lock', role: 'Final policy & actions', state: 'pending', latency: null, detail: '' },
    ]);

    // Reset graph state
    this.activePath.set('none');
    this.activePathSegments.set([]);
    this.packetKey.set(0);

    this.apiService.simulateMessage(text, this.simulationLanguage()).subscribe({
      next: (res) => {
        const result: SimulationUiResult = {
          detectedLanguage: res.language || 'en',
          toxicityScore: res.toxicity_score,
          llmTriggered: res.llm_triggered,
          behavioralScore: res.behavioral_risk_score || 0,
          finalScore: res.final_score,
          decision: res.decision?.toLowerCase(),
          explanation: res.llm_explanation || res.explanation || 'Pipeline analysis complete.',
          agentLatencies: res.agent_latencies || { agent_1_2: 0, agent_3: 0, agent_4: 0, agent_5: 0 },
          needsAudit: res.needs_audit || false,
          escalationRisk: res.escalation_risk || 0,
          mlCorrected: res.ml_corrected || false,
          category: res.primary_class || 'safe',
          isDarija: res.is_darija || false,
          darijaScript: res.darija_script || null,
        };
        this.simulationResult.set(result);
        this.animatePipelineFlow(result);
      },
      error: () => {
        this.isSimulating.set(false);
        this.messageService.add({ severity: 'error', summary: 'Simulation Failed', detail: 'Could not reach the pipeline' });
      }
    });
  }

  get routeLabel(): string {
    const r = this.simulationResult();
    if (!r) return '';
    if (r.isDarija) return 'Darija Track (M1D)';
    return r.llmTriggered ? 'Audit Path' : 'Fast Path';
  }

  get routeColor(): string {
    const r = this.simulationResult();
    if (!r) return 'var(--text-muted)';
    if (r.isDarija) return '#8b5cf6';
    return r.llmTriggered ? '#f59e0b' : '#10b981';
  }

  private animatePipelineFlow(result: SimulationUiResult): void {
    const lat = result.agentLatencies;
    const isAudit = result.llmTriggered;
    const modelLabel = result.isDarija ? 'M1D (DarijaBERT)' : 'M1+M2';
    const scriptTag = result.darijaScript ? ` [${result.darijaScript}]` : '';
    const d = 250;  // initial delay
    const s = 420;  // step duration

    // Set the routing path
    this.activePath.set(isAudit ? 'audit' : 'fast');

    // ═══ Phase 1: Agent 1+2 (Pipeline) ═══
    this.animationTimers.push(setTimeout(() => {
      this.updateNode(0, 'active', lat.agent_1_2, `${modelLabel}${scriptTag} → ${result.toxicityScore.toFixed(2)}`);
      this.activePathSegments.set(['entry']);
    }, d));

    this.animationTimers.push(setTimeout(() => {
      this.updateNode(0, 'completed', lat.agent_1_2, `${modelLabel}${scriptTag} → ${result.toxicityScore.toFixed(2)}`);
      this.activePathSegments.update(p => [...p, isAudit ? 'toAuditor' : 'toFast']);
      this.packetKey.update(k => k + 1);
    }, d + s));

    // ═══ Phase 2: Conditional Routing ═══
    if (isAudit) {
      // AUDIT PATH: Agent 3 activates
      this.animationTimers.push(setTimeout(() => {
        this.updateNode(1, 'active', lat.agent_3, 'Auditing...');
      }, d + s * 2));

      this.animationTimers.push(setTimeout(() => {
        const correction = result.mlCorrected ? ' ✓ Corrected' : '';
        this.updateNode(1, 'completed', lat.agent_3, `LLM reviewed${correction}`);
        this.activePathSegments.update(p => [...p, 'toProfiler']);
        this.packetKey.update(k => k + 1);
      }, d + s * 3));
    } else {
      // FAST PATH: Agent 3 skipped
      this.animationTimers.push(setTimeout(() => {
        this.updateNode(1, 'skipped', 0, 'Skipped — high confidence');
      }, d + s * 2));
    }

    // ═══ Phase 3: Agent 4 (Profiler) ═══
    const p4Start = isAudit ? d + s * 4 : d + s * 3;
    this.animationTimers.push(setTimeout(() => {
      this.updateNode(2, 'active', lat.agent_4, `Risk: ${result.behavioralScore.toFixed(2)}`);
    }, p4Start));

    this.animationTimers.push(setTimeout(() => {
      this.updateNode(2, 'completed', lat.agent_4, `Risk: ${result.behavioralScore.toFixed(2)}`);
      this.activePathSegments.update(p => [...p, 'toEnforcer']);
      this.packetKey.update(k => k + 1);
    }, p4Start + s));

    // ═══ Phase 4: Agent 5 (Enforcer) ═══
    const p5Start = p4Start + s * 2;
    this.animationTimers.push(setTimeout(() => {
      this.updateNode(3, 'active', lat.agent_5, 'Deciding...');
    }, p5Start));

    this.animationTimers.push(setTimeout(() => {
      this.updateNode(3, 'completed', lat.agent_5, `Decision: ${result.decision.toUpperCase()}`);
      this.isSimulating.set(false);
    }, p5Start + s));
  }

  private updateNode(index: number, state: PipelineNodeState['state'], latency: number | null, detail: string): void {
    this.pipelineNodes.update(nodes => 
      nodes.map((n, i) => i === index ? { ...n, state, latency, detail } : n)
    );
  }

  getDecisionIcon(decision: string): string {
    switch (decision) {
      case 'allow': return 'pi-check-circle';
      case 'warn': return 'pi-exclamation-triangle';
      case 'escalate': return 'pi-arrow-up';
      case 'block': return 'pi-ban';
      case 'critical': return 'pi-exclamation-circle';
      default: return 'pi-question';
    }
  }

  readonly totalLatency = computed(() => {
    const r = this.simulationResult();
    if (!r) return 0;
    const l = r.agentLatencies;
    return (l.agent_1_2 || 0) + (l.agent_3 || 0) + (l.agent_4 || 0) + (l.agent_5 || 0);
  });

  getNodeElapsed(index: number): number {
    const r = this.simulationResult();
    if (!r) return 0;
    const l = r.agentLatencies;
    const arr = [l.agent_1_2, l.agent_3, l.agent_4, l.agent_5];
    let sum = 0;
    for (let i = 0; i <= index; i++) sum += (arr[i] || 0);
    return sum;
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

  getCategoryLabel(category?: string): string {
    if (!category) return 'Safe';
    const c = category.toLowerCase();
    if (c === 'grooming' || c === 'sexual') return 'Sexual Harassment';
    if (c === 'insult') return 'Insult / Bullying';
    if (c === 'threat') return 'Threat';
    if (c === 'profanity') return 'Profanity';
    if (c === 'safe') return 'Safe';
    return category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' ');
  }

  private detectLanguage(text: string): 'fr' | 'ar' | 'en' | 'darija' {
    // Arabizi digit patterns (3=ع, 7=ح, etc.) suggest Darija
    if (/\b\d{1,2}[a-z]+|[a-z]+\d+[a-z]*\b/.test(text)) return 'darija';
    if (/[\u0600-\u06ff]/.test(text)) return 'ar';
    if (text.includes('je ') || text.includes('toi') || text.includes('bonjour')) return 'fr';
    return 'en';
  }

  private clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
  }

  // ════════════════════════════════════════════════════════════
  //  BN BRAIN MAP METHODS
  // ════════════════════════════════════════════════════════════

  loadBnContacts(): void {
    this.apiService.getAdminRiskProfiles().subscribe({
      next: (data) => {
        const contacts: ContactOption[] = [];
        if (data.contacts) {
          for (const c of data.contacts) {
            contacts.push({ jid: c.raw_jid || c.id, label: c.display_name || c.raw_jid || c.id });
          }
        }
        this.bnContacts.set(contacts);
      },
      error: () => console.error('Failed to load contacts for BN visualization'),
    });
  }

  initBnCustomEvidence(): void {
    const evidence: Record<string, string> = {};
    for (const obs of BN_OBSERVABLES) {
      evidence[obs.id] = obs.states[0];
    }
    this.bnCustomEvidence.set(evidence);
  }

  toggleBnMode(): void {
    const next = !this.bnCustomMode();
    this.bnCustomMode.set(next);
    if (next) {
      this.initBnCustomEvidence();
    }
  }

  setBnCustomState(obsId: string, state: string): void {
    this.bnCustomEvidence.update(ev => ({ ...ev, [obsId]: state }));
  }

  runBnInference(): void {
    this.bnError.set(null);
    this.bnIsRunning.set(true);
    this.bnHasResult.set(false);

    // Reset all nodes to idle
    this.bnObservables.update(nodes => nodes.map(n => ({ ...n, animPhase: 'idle' as const })));
    this.bnPathwayNodes.update(nodes => nodes.map(n => ({ ...n, animPhase: 'idle' as const, probs: {} })));
    this.bnOverall.set({ probs: {}, riskScore: 0, riskLevel: 'LOW', archetype: 'Normal User', animPhase: 'idle' });

    const payload = this.bnCustomMode()
      ? { evidence: this.bnCustomEvidence() }
      : { sender_jid: this.bnSelectedContact() };

    if (!this.bnCustomMode() && !this.bnSelectedContact()) {
      this.bnIsRunning.set(false);
      this.bnError.set('Please select a contact or switch to Custom Evidence mode.');
      return;
    }

    this.apiService.runBnInference(payload).subscribe({
      next: (res) => this.animateBnInference(res),
      error: (err) => {
        this.bnIsRunning.set(false);
        this.bnError.set(err.error?.error || 'Failed to run BN inference. Check backend.');
      },
    });
  }

  private animateBnInference(res: any): void {
    // Clear previous timers
    this.animationTimers.forEach(t => clearTimeout(t));
    this.animationTimers = [];

    // Phase 1: Build observable nodes with evidence state (immediate)
    const obsNodes: BnObservableNode[] = BN_OBSERVABLES.map(def => ({
      id: def.id,
      label: def.label,
      state: res.evidence[def.id] || def.states[0],
      states: def.states,
      priors: res.observables?.find((o: any) => o.name === def.id)?.priors || {},
      pathway: def.pathway,
      animPhase: 'idle' as const,
    }));
    this.bnObservables.set(obsNodes);

    // Phase 2: Build pathway nodes (will animate later)
    const pathwayNodes: BnPathwayNode[] = BN_PATHWAYS.map(def => ({
      id: def.id,
      label: def.label,
      color: def.color,
      probs: {},
      highProb: 0,
      animPhase: 'idle' as const,
    }));
    this.bnPathwayNodes.set(pathwayNodes);

    // Animate cascade
    const d = 100; // initial delay

    // Phase 1: Observables light up one by one (0-400ms)
    obsNodes.forEach((_, i) => {
      this.animationTimers.push(setTimeout(() => {
        this.bnObservables.update(nodes =>
          nodes.map((n, idx) => idx === i ? { ...n, animPhase: 'active' } : n)
        );
      }, d + i * 35));
    });

    // Settle all observables
    this.animationTimers.push(setTimeout(() => {
      this.bnObservables.update(nodes => nodes.map(n => ({ ...n, animPhase: 'settled' })));
    }, d + obsNodes.length * 35 + 150));

    // Phase 2: Pathways compute (600-1000ms)
    const pathwayDelay = d + obsNodes.length * 35 + 300;
    BN_PATHWAYS.forEach((def, i) => {
      this.animationTimers.push(setTimeout(() => {
        const probs = res.pathways[def.id] || {};
        this.bnPathwayNodes.update(nodes =>
          nodes.map(n => n.id === def.id ? { ...n, probs, highProb: probs['HIGH'] || 0, animPhase: 'computing' } : n)
        );
      }, pathwayDelay + i * 150));
    });

    // Settle pathways
    this.animationTimers.push(setTimeout(() => {
      this.bnPathwayNodes.update(nodes => nodes.map(n => ({ ...n, animPhase: 'settled' })));
    }, pathwayDelay + BN_PATHWAYS.length * 150 + 200));

    // Phase 3: Overall risk resolves (after pathways)
    const overallDelay = pathwayDelay + BN_PATHWAYS.length * 150 + 400;
    this.animationTimers.push(setTimeout(() => {
      this.bnOverall.set({
        probs: res.overall || {},
        riskScore: res.risk_score || 0,
        riskLevel: res.risk_level || 'LOW',
        archetype: res.archetype || 'Normal User',
        animPhase: 'computing',
      });
    }, overallDelay));

    this.animationTimers.push(setTimeout(() => {
      this.bnOverall.update(o => ({ ...o, animPhase: 'settled' }));
      this.bnIsRunning.set(false);
      this.bnHasResult.set(true);
    }, overallDelay + 300));
  }

  getPathwayColor(pathwayKey: string): string {
    return BN_PATHWAY_COLORS[pathwayKey] || '#64748b';
  }

  getBnPathwayForEdge(toId: string): string {
    const p = BN_PATHWAYS.find(pw => pw.id === toId);
    if (p) return p.color;
    if (toId === 'OverallRisk') return '#3b82f6';
    return '#64748b';
  }

  /** Returns the primary pathway color for an observable (first pathway) */
  getObsPrimaryColor(obs: BnObservableNode): string {
    if (!obs.pathway.length) return '#64748b';
    return this.getPathwayColor(obs.pathway[0]);
  }

  formatPct(val: number): string {
    return (val * 100).toFixed(1) + '%';
  }

  getRiskLevelColor(level: string): string {
    const map: Record<string, string> = {
      'LOW': '#10b981', 'MEDIUM': '#f59e0b', 'HIGH': '#f97316', 'CRITICAL': '#ef4444',
    };
    return map[level] || '#64748b';
  }

  getArchetypeIcon(archetype: string): string {
    const map: Record<string, string> = {
      'Normal User': 'pi-check-circle', 'Troll Pattern': 'pi-comment',
      'Bully Pattern': 'pi-bolt', 'Groomer Pattern': 'pi-eye',
    };
    return map[archetype] || 'pi-question-circle';
  }

  getArchetypeColor(archetype: string): string {
    const map: Record<string, string> = {
      'Normal User': '#10b981', 'Troll Pattern': '#8b5cf6',
      'Bully Pattern': '#f59e0b', 'Groomer Pattern': '#f43f5e',
    };
    return map[archetype] || '#64748b';
  }
}
