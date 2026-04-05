import { Component, signal, effect, inject, ElementRef, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';

export interface ChatMessage {
  id: string;
  role: 'bot' | 'user';
  text: string;
  sources?: string[];
  isTyping?: boolean;
}

@Component({
  selector: 'app-chatbot-widget',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chatbot-widget.html',
  styleUrl: './chatbot-widget.css',
})
export class ChatbotWidgetComponent implements OnDestroy {
  private router = inject(Router);
  private elRef = inject(ElementRef);

  isOpen = signal(false);
  showPulse = signal(true);
  chatLanguage = signal<'fr' | 'ar' | 'en'>(this.getSystemLanguage());
  isFullPage = signal(false);
  isResizing = signal(false);

  // Panel dimensions  – start at industry-standard Intercom/Crisp size
  panelW = signal(380);
  panelH = signal(520);

  private MIN_W = 300;
  private MAX_W = 600;
  private MIN_H = 400;
  private MAX_H = 700;

  private resizeStartX = 0;
  private resizeStartY = 0;
  private resizeStartW = 0;
  private resizeStartH = 0;

  private onMouseMove = (e: MouseEvent) => {
    const dw = this.resizeStartX - e.clientX; // drag left → wider
    const dh = this.resizeStartY - e.clientY; // drag up → taller
    this.panelW.set(Math.min(this.MAX_W, Math.max(this.MIN_W, this.resizeStartW + dw)));
    this.panelH.set(Math.min(this.MAX_H, Math.max(this.MIN_H, this.resizeStartH + dh)));
  };

  private onMouseUp = () => {
    this.isResizing.set(false);
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('mouseup', this.onMouseUp);
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
  };

  startResize(e: MouseEvent) {
    e.preventDefault();
    this.isResizing.set(true);
    this.resizeStartX = e.clientX;
    this.resizeStartY = e.clientY;
    this.resizeStartW = this.panelW();
    this.resizeStartH = this.panelH();
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'nwse-resize';
    document.addEventListener('mousemove', this.onMouseMove);
    document.addEventListener('mouseup', this.onMouseUp);
  }

  messages = signal<ChatMessage[]>([
    {
      id: '1',
      role: 'bot',
      text: "Bonjour ! Je suis l'Assistant AEGIS, alimenté par la base de connaissance RAG. Comment puis-je vous aider ?",
    },
  ]);

  inputText = '';
  isInputFocused = signal(false);
  isTyping = signal(false);

  contextChips = signal<string[]>([
    'Quelles lois protègent les mineurs ?',
    'Comment signaler un contenu ?',
    'Définition légale du harcèlement',
  ]);

  constructor() {
    this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe((e: any) => {
        this.updateContextChips(e.urlAfterRedirects);
        this.isFullPage.set(e.urlAfterRedirects.includes('/admin/chatbot'));
      });

    effect(
      () => {
        if (this.isOpen()) this.showPulse.set(false);
      },
      { allowSignalWrites: true },
    );
  }

  ngOnDestroy() {
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('mouseup', this.onMouseUp);
  }

  toggleChat() {
    this.isOpen.update((v) => !v);
  }

  openFullChat() {
    this.isOpen.set(false);
    this.router.navigate(['/admin/chatbot']);
  }

  private getSystemLanguage(): 'fr' | 'ar' | 'en' {
    const lang = navigator.language.split('-')[0];
    if (['fr', 'ar', 'en'].includes(lang)) return lang as any;
    return 'fr';
  }

  setLanguage(lang: 'fr' | 'ar' | 'en') {
    this.chatLanguage.set(lang);
  }

  sendChip(chip: string) {
    this.sendMessage(chip);
  }

  sendMessage(overrideText?: string) {
    const text = (overrideText ?? this.inputText).trim();
    if (!text) return;
    this.inputText = '';

    this.messages.update((m) => [...m, { id: crypto.randomUUID(), role: 'user', text }]);
    this.isTyping.set(true);

    const typingId = crypto.randomUUID();
    this.messages.update((m) => [...m, { id: typingId, role: 'bot', text: '', isTyping: true }]);

    // Final response content
    const fullText = "D'après la loi 103-13 et le guide UNICEF, le cyberharcèlement est défini comme tout comportement répété portant atteinte à la dignité d'un mineur via des moyens numériques.";
    const sources = ['Loi 103-13', 'Guide UNICEF'];

    setTimeout(() => {
      // Remove typing indicator and add a placeholder bot message
      const botMsgId = crypto.randomUUID();
      this.messages.update((m) => [
        ...m.filter((msg) => msg.id !== typingId),
        { id: botMsgId, role: 'bot', text: '', sources: [] },
      ]);
      this.isTyping.set(false);

      // Start streaming characters
      let currentText = '';
      const words = fullText.split(' ');
      let i = 0;

      const interval = setInterval(() => {
        if (i < words.length) {
          currentText += (i === 0 ? '' : ' ') + words[i];
          this.updateBotMessage(botMsgId, currentText);
          this.scrollToBottom();
          i++;
        } else {
          clearInterval(interval);
          // Add sources at the end
          this.updateBotMessage(botMsgId, currentText, sources);
          this.scrollToBottom();
        }
      }, 40);
    }, 1000);

    this.scrollToBottom();
  }

  private updateBotMessage(id: string, text: string, sources?: string[]) {
    this.messages.update((m) =>
      m.map((msg) => (msg.id === id ? { ...msg, text, sources: sources ?? msg.sources } : msg)),
    );
  }

  private updateContextChips(url: string) {
    if (url.includes('/admin/alerts')) {
      this.contextChips.set(['Qu\'est-ce que le harcèlement verbal ?', 'Gérer une alerte CRITIQUE ?', 'Procédure d\'escalade']);
    } else if (url.includes('/admin/risk-profiles')) {
      this.contextChips.set(['Que signifie un score > 0.8 ?', 'Comment est calculé le score ?', 'Quand notifier les parents ?']);
    } else if (url.includes('/admin/resources')) {
      this.contextChips.set(['Dernier guide importé', 'Lois dans FAISS ?', 'Métrique Context Precision']);
    } else {
      this.contextChips.set(['Quelles lois protègent les mineurs ?', 'Comment signaler un contenu ?', 'Définition légale du harcèlement']);
    }
  }

  private scrollToBottom() {
    setTimeout(() => {
      const el = document.getElementById('widget-messages');
      if (el) el.scrollTop = el.scrollHeight;
    }, 60);
  }
}
