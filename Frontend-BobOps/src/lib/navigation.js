export function viewTransitionPush(router, to) {
  if (document.startViewTransition) {
    document.startViewTransition(() => router.push(to))
  } else {
    router.push(to)
  }
}
