import { Component, input } from '@angular/core';
import { CardModule } from 'primeng/card';

@Component({
  selector: 'app-card',
  standalone: true,
  imports: [CardModule],
  template: `
    <p-card [header]="header()" styleClass="shadow-sm">
      <ng-content />
    </p-card>
  `,
})
export class CardComponent {
  header = input('');
}
