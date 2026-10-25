// The official toolkit rejects custom forge hostnames before trying its v4 API.
// Apply its hosted-mode probe only to artifact actions using our local service.
const repository = process.env.GITHUB_ACTION_REPOSITORY
const results = process.env.ACTIONS_RESULTS_URL
if (
  ["actions/upload-artifact", "actions/download-artifact"].includes(repository || "") &&
  results &&
  new URL(results).hostname === "127.0.0.1"
) {
  process.env.GITHUB_SERVER_URL = "https://github.com"
}
