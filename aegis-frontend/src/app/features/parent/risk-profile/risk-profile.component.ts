import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { getRiskHex } from '@shared/utils/severity.utils';

@Component({
  selector: 'app-risk-profile',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './risk-profile.html',
  styleUrl: './risk-profile.css'
})
export class RiskProfileComponent implements OnInit {
  childName = 'Emma L.';
  childNumber = '+1 555-0199-823';
  currentRiskScore = 0.54;
  currentRiskLevel = 'medium';
  
  threatActors = [
    { id: '1', name: 'Unknown Target', number: '+1 555-1234-567', score: 0.88, level: 'high', patterns: ['Profanity', 'Late Night'] },
    { id: '2', name: 'Jake', number: '+1 555-9876-543', score: 0.42, level: 'medium', patterns: ['Spam', 'Anxious Tone'] },
    { id: '3', name: 'Marketing Bot', number: '+1 800-555-0000', score: 0.12, level: 'low', patterns: ['Promotional'] }
  ];

  getRiskHex = getRiskHex;

  ngOnInit() {
  }
}
