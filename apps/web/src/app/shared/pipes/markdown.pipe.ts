import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/**
 * Autor: Carlos Adriano
 * Data: 2026-08-12
 * Descrição: Renderiza o subconjunto de markdown que o Agente de IA
 * pode usar na resposta (negrito, itálico, código inline, listas,
 * parágrafos) como HTML sanitizado — layout replicado do projeto
 * irmão (`frontend/src/app/pipes/markdown.pipe.ts`). Escapa entidades
 * HTML antes de aplicar as substituições, então texto do usuário/IA
 * nunca injeta markup arbitrário; o único HTML gerado é o produzido
 * pelas regras abaixo, sempre passado por `bypassSecurityTrustHtml`
 * depois de já estar seguro.
 */
@Pipe({
  name: 'markdown',
  standalone: true,
  pure: true,
})
export class MarkdownPipe implements PipeTransform {
  private readonly sanitizer = inject(DomSanitizer);

  /**
   * Autor: Carlos Adriano
   * Data: 2026-08-12
   * Descrição: Converte negrito (`**x**`), itálico (`*x*`), código
   * inline (`` `x` ``), listas (`- `/`1. `) e parágrafos (linha em
   * branco) em HTML. Sem suporte a headings/links/tabelas — não são
   * esperados nas respostas do agente (instrução de sistema em
   * `generate_ai_response.py`).
   */
  transform(value: string | null | undefined): SafeHtml {
    if (!value) {
      return '';
    }

    let html = value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    html = html.replace(/((?:^[•-] .+\n?)+)/gm, (block) => {
      const items = block
        .split('\n')
        .filter((line) => line.trim())
        .map((line) => `<li>${line.replace(/^[•-] /, '')}</li>`)
        .join('');
      return `<ul>${items}</ul>`;
    });
    html = html.replace(/((?:^\d+\. .+\n?)+)/gm, (block) => {
      const items = block
        .split('\n')
        .filter((line) => line.trim())
        .map((line) => `<li>${line.replace(/^\d+\. /, '')}</li>`)
        .join('');
      return `<ol>${items}</ol>`;
    });

    html = html
      .split(/\n{2,}/)
      .map((paragraph) => {
        const trimmed = paragraph.trim();
        if (!trimmed) {
          return '';
        }
        if (/^<(ul|ol|li)/.test(trimmed)) {
          return trimmed;
        }
        return `<p>${trimmed.replace(/\n/g, '<br>')}</p>`;
      })
      .filter(Boolean)
      .join('');

    return this.sanitizer.bypassSecurityTrustHtml(html);
  }
}
