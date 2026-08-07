export default function AppLoading() {
  return <main id="main-content" className="app-shell loading-state" aria-busy="true" tabIndex={-1}>
    <div role="status" aria-live="polite" aria-atomic="true">
      <span className="loading-indicator" aria-hidden="true"/>
      <p>Cargando / Loading…</p>
    </div>
  </main>;
}
