import { Component, input } from '@angular/core';
import { ButtonModule } from 'primeng/button';

@Component({
  selector: 'app-button',
  standalone: true,
  imports: [ButtonModule],
  template: `
    <p-button [label]="label()" [severity]="severity()" [disabled]="disabled()" [icon]="icon()" />
  `,
})
export class ButtonComponent {
  label = input('');
  severity = input<'primary' | 'secondary' | 'success' | 'danger' | undefined>(undefined);
  disabled = input(false);
  icon = input('');
}
