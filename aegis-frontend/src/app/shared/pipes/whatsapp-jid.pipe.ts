import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'whatsappJid',
  standalone: true
})
export class WhatsappJidPipe implements PipeTransform {
  transform(value: string | undefined | null): string {
    if (!value) return '';
    
    // Strip the @s.whatsapp.net or @lid part
    let num = value.split('@')[0];
    
    // If it's not numbers (like a group ID), just return it
    if (!/^\d+$/.test(num)) {
      return num;
    }
    
    // Format nice phone numbers (assumes typical lengths)
    // Example: 212786814288 -> +212 786-814288
    // Or simpler: just + and the number, with a space after country code
    if (num.length > 4) {
      if (num.startsWith('212')) {
        // Moroccan format: +212 6 XX XX XX XX
        const rest = num.substring(3);
        const formattedRest = rest.match(/.{1,2}/g)?.join(' ') || rest;
        return `+212 ${formattedRest}`;
      } else if (num.startsWith('33')) {
        // French format: +33 6 XX XX XX XX
        const rest = num.substring(2);
        const formattedRest = rest.match(/.{1,2}/g)?.join(' ') || rest;
        return `+33 ${formattedRest}`;
      } else {
        // Generic fallback: +XXX XXXXXXX
        return `+${num.substring(0, 3)} ${num.substring(3)}`;
      }
    }
    
    return `+${num}`;
  }
}
