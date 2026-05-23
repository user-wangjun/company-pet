import type { Point } from '../pet-core/perchPlanner';
import type { DesktopInteractionContext } from '../pet-core/interactionGate';

export type DesktopContextInvoker = (
  command: 'desktop_interaction_context_at',
  args: { x: number; y: number },
) => Promise<DesktopInteractionContext>;

const UNKNOWN_DESKTOP_CONTEXT: DesktopInteractionContext = {
  surface: 'unknown',
  allowUnknown: true,
};

export async function readDesktopInteractionContext(
  pointer: Point,
  invoker?: DesktopContextInvoker,
): Promise<DesktopInteractionContext> {
  const resolvedInvoker = invoker ?? (await loadTauriInvoker());
  if (!resolvedInvoker) {
    return UNKNOWN_DESKTOP_CONTEXT;
  }

  try {
    return await resolvedInvoker('desktop_interaction_context_at', {
      x: Math.round(pointer.x),
      y: Math.round(pointer.y),
    });
  } catch {
    return UNKNOWN_DESKTOP_CONTEXT;
  }
}

async function loadTauriInvoker(): Promise<DesktopContextInvoker | null> {
  if (typeof window === 'undefined' || !('__TAURI_INTERNALS__' in window)) {
    return null;
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return (command, args) => invoke<DesktopInteractionContext>(command, args);
  } catch {
    return null;
  }
}
