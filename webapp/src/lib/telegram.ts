/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    Telegram?: {
      WebApp: any;
    };
  }
}

let _inited = false;

export function getTg(): any | null {
  return (window as any).Telegram?.WebApp || null;
}

export function initTelegram(): { isTelegram: boolean } {
  const tg = getTg();
  if (tg && !_inited) {
    try {
      tg.ready?.();
      tg.expand?.();
      tg.enableClosingConfirmation?.();
      _inited = true;
    } catch {}
  }
  return { isTelegram: !!tg };
}

export function syncTheme(setTheme: (theme: 'light' | 'dark') => void) {
  const tg = getTg();
  if (!tg) return;
  const apply = () => {
    const t = tg.colorScheme || 'light';
    setTheme(t);
    document.documentElement.setAttribute('data-theme', t);
    if (tg.themeParams) {
      // apply some vars if needed
    }
  };
  apply();
  tg.onEvent?.('themeChanged', apply);
}

export function setupBackButton(back: () => void, show: boolean) {
  const tg = getTg();
  if (!tg?.BackButton) return;
  try {
    if (show) {
      tg.BackButton.show();
      tg.BackButton.onClick(back);
    } else {
      tg.BackButton.hide();
    }
  } catch {}
}

export function setupMainButton(opts: { text?: string; onClick?: () => void; visible?: boolean }) {
  const tg = getTg();
  const mb = tg?.MainButton;
  if (!mb) return;
  try {
    if (opts.visible === false) {
      mb.hide();
      return;
    }
    if (opts.text) mb.setText(opts.text);
    if (opts.onClick) {
      // remove previous if possible, but TG API is limited; caller should manage
      mb.onClick(opts.onClick);
    }
    mb.show();
  } catch {}
}

export function haptic(type: 'success' | 'error' | 'warning' | 'light' | 'medium' | 'heavy' = 'success') {
  const tg = getTg();
  try {
    if (type === 'success' || type === 'error' || type === 'warning') {
      tg?.HapticFeedback?.notificationOccurred?.(type);
    } else {
      tg?.HapticFeedback?.impactOccurred?.(type);
    }
  } catch {}
}
