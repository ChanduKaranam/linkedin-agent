export function buildLinkedInAuthorizeUrl(returnTo?: string): string {
  const current = returnTo ?? `${window.location.pathname}${window.location.search}`;
  return `/api/admin/linkedin/authorize?return_to=${encodeURIComponent(current)}`;
}
