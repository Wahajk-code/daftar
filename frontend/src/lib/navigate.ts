/** Go to another screen with a full page load, so the server draws it with the session as it is now. */
export function navigate(path: string): void {
  window.location.href = new URL(path, window.location.origin).href;
}
