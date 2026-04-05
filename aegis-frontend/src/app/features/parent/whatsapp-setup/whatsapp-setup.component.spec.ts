import { ComponentFixture, TestBed } from '@angular/core/testing';

import { WhatsappSetup } from './whatsapp-setup';

describe('WhatsappSetup', () => {
  let component: WhatsappSetup;
  let fixture: ComponentFixture<WhatsappSetup>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [WhatsappSetup],
    }).compileComponents();

    fixture = TestBed.createComponent(WhatsappSetup);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
