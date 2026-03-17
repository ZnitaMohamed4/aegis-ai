import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ConversationViewer } from './conversation-viewer';

describe('ConversationViewer', () => {
  let component: ConversationViewer;
  let fixture: ComponentFixture<ConversationViewer>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConversationViewer],
    }).compileComponents();

    fixture = TestBed.createComponent(ConversationViewer);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
