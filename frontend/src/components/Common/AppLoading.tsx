const AppLoading = () => (
  <div className="app-opening" role="status" aria-label="Opening GitEdge">
    <div>
      <div className="app-opening-mark" aria-hidden="true">
        G
      </div>
      <p className="app-opening-title">GitEdge</p>
      <div className="app-opening-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <p className="app-opening-caption">Opening your workspace…</p>
    </div>
  </div>
)

export default AppLoading
