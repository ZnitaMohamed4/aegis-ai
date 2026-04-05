import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ChatbotPage } from './chatbot-page';

describe('ChatbotPage', () => {
  let component: ChatbotPage;
  let fixture: ComponentFixture<ChatbotPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatbotPage],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatbotPage);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
