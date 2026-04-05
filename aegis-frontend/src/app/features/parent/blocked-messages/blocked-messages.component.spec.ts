import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BlockedMessages } from './blocked-messages';

describe('BlockedMessages', () => {
  let component: BlockedMessages;
  let fixture: ComponentFixture<BlockedMessages>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BlockedMessages],
    }).compileComponents();

    fixture = TestBed.createComponent(BlockedMessages);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
