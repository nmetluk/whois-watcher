/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { Icon } from '../components/Icon';

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

export function statusOf(d: any) {
  if (d.isWishlist) return { key: 'wish', label: 'Wishlist', color: 'wish', dot: 'var(--pv-violet)' };
  if (d.noData || d.daysLeft == null) return { key: 'gray', label: 'Нет данных', color: 'gray', dot: 'var(--pv-fg-subtle)' };
  if (d.daysLeft < 0) return { key: 'red', label: 'Истёк', color: 'red', dot: 'var(--pv-red)' };
  if (d.daysLeft < 7) return { key: 'red', label: 'Критично', color: 'red', dot: 'var(--pv-red)' };
  if (d.daysLeft < 30) return { key: 'gold', label: 'Скоро', color: 'gold', dot: 'var(--pv-gold)' };
  return { key: 'green', label: 'В норме', color: 'green', dot: 'var(--pv-green)' };
}

export function daysText(d: any) {
  if (d.isWishlist) return 'жду освобождения';
  if (d.daysLeft == null) return 'нет данных';
  if (d.daysLeft < 0) return `истёк ${-d.daysLeft} дн. назад`;
  if (d.daysLeft === 0) return 'истекает сегодня';
  return `через ${d.daysLeft} ${plural(d.daysLeft, 'день', 'дня', 'дней')}`;
}

export function puckText(d: any) {
  if (d.isWishlist) return React.createElement(Icon as any, { name: 'target', style: { fontSize: 18 } });
  if (d.daysLeft == null) return '—';
  if (d.daysLeft < 0) return React.createElement(Icon as any, { name: 'error', style: { fontSize: 18 } });
  return React.createElement('span', null, d.daysLeft, React.createElement('small', null, 'дн'));
}
