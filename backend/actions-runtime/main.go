// GitEdge's one-shot job executor. Workloads only run inside a job sandbox.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/nektos/act/pkg/artifactcache"
	"github.com/nektos/act/pkg/artifacts"
	"github.com/nektos/act/pkg/common"
	"github.com/nektos/act/pkg/model"
	"github.com/nektos/act/pkg/runner"
	log "github.com/sirupsen/logrus"
)

type dependency struct {
	Result  string            `json:"result"`
	Outputs map[string]string `json:"outputs"`
}
type input struct {
	Workflow  string                 `json:"workflow"`
	Job       string                 `json:"job"`
	Matrix    map[string]interface{} `json:"matrix"`
	Needs     map[string]dependency  `json:"needs"`
	Event     map[string]interface{} `json:"event"`
	EventName string                 `json:"event_name"`
	Actor     string                 `json:"actor"`
	Env       map[string]string      `json:"env"`
	Secrets   map[string]string      `json:"secrets"`
	Vars      map[string]string      `json:"vars"`
}
type result struct {
	Status  string                       `json:"status"`
	Outputs map[string]string            `json:"outputs"`
	Steps   map[string]*model.StepResult `json:"steps"`
	Error   string                       `json:"error,omitempty"`
}

// bakedActionCache never clones or downloads an action during a job.
type bakedActionCache struct{}

func (bakedActionCache) Fetch(ctx context.Context, cacheDir, url, ref, token string) (string, error) {
	raw, err := os.ReadFile("/opt/gitedge/action-cache/manifest.json")
	if err != nil {
		return "", err
	}
	manifest := map[string]string{}
	if err = json.Unmarshal(raw, &manifest); err != nil {
		return "", err
	}
	sha, ok := manifest[cacheDir+"@"+ref]
	if !ok {
		return "", fmt.Errorf("action %s@%s is not prepared in this image; rebuild the action image before dispatch", cacheDir, ref)
	}
	return sha, nil
}
func (bakedActionCache) GetTarArchive(ctx context.Context, cacheDir, sha, prefix string) (io.ReadCloser, error) {
	return (runner.GoGitActionCache{Path: filepath.Clean("/opt/gitedge/action-cache")}).GetTarArchive(ctx, cacheDir, sha, prefix)
}

func execute() (result, error) {
	raw, err := os.ReadFile("/gitedge/input.json")
	if err != nil {
		return result{}, err
	}
	var in input
	if err = json.Unmarshal(raw, &in); err != nil {
		return result{}, err
	}
	wf, err := model.ReadWorkflow(strings.NewReader(in.Workflow), false)
	if err != nil {
		return result{}, err
	}
	job := wf.Jobs[in.Job]
	if job == nil {
		return result{}, fmt.Errorf("unknown job %s", in.Job)
	}
	for key, need := range in.Needs {
		wf.Jobs[key].Result = need.Result
		wf.Jobs[key].Outputs = need.Outputs
	}
	// GitEdge already assigned one matrix variant to this sandbox.
	job.Strategy = nil
	job.Result = ""
	event, err := json.Marshal(in.Event)
	if err != nil {
		return result{}, err
	}
	cfg := &runner.Config{
		Actor: in.Actor, Workdir: "/gitedge/source", ActionCacheDir: "/gitedge/actions", ActionCache: bakedActionCache{}, NoSkipCheckout: true, Token: in.Secrets["GITHUB_TOKEN"],
		EventName: in.EventName, Env: in.Env, Secrets: in.Secrets, Vars: in.Vars,
		GitHubInstance: "github.com", RemoteName: "origin", JSONLogger: true,
		LogOutput: true, AutoRemove: true, ContainerDaemonSocket: "-",
		ArtifactServerPath: "/gitedge/state/artifacts", ArtifactServerAddr: "127.0.0.1", ArtifactServerPort: "34567",
		Platforms: map[string]string{"ubuntu-latest": "-self-hosted", "ubuntu-24.04": "-self-hosted", "ubuntu-22.04": "-self-hosted", "self-hosted": "-self-hosted"},
	}
	ctx := common.WithJobErrorContainer(context.Background())
	cache, err := artifactcache.StartHandler("/gitedge/state/cache", "", "127.0.0.1", 0, nil)
	if err != nil {
		return result{}, err
	}
	defer cache.Close()
	cfg.Env["ACTIONS_CACHE_URL"] = cache.ExternalURL() + "/"
	cancelArtifacts := artifacts.Serve(ctx, cfg.ArtifactServerPath, cfg.ArtifactServerAddr, cfg.ArtifactServerPort)
	defer cancelArtifacts()
	rc := &runner.RunContext{
		Config: cfg, Run: &model.Run{Workflow: wf, JobID: in.Job},
		EventJSON: string(event), Matrix: in.Matrix, StepResults: make(map[string]*model.StepResult),
	}
	rc.ExprEval = rc.NewExpressionEvaluator(ctx)
	rc.Name = rc.ExprEval.Interpolate(ctx, rc.Run.String())
	ctx = runner.WithJobLogger(ctx, in.Job, rc.Name, cfg, &rc.Masks, in.Matrix)
	exec, err := rc.Executor()
	if err != nil {
		return result{}, err
	}
	err = exec(ctx)
	res := result{Status: job.Result, Outputs: job.Outputs, Steps: rc.StepResults}
	if err != nil {
		res.Status = "failure"
		res.Error = err.Error()
	}
	if res.Status == "" {
		res.Status = "failure"
		res.Error = "job did not produce a result (unsupported platform)"
	}
	return res, nil
}

func main() {
	log.SetLevel(log.InfoLevel)
	res, err := execute()
	if err != nil {
		res = result{Status: "failure", Error: err.Error()}
	}
	raw, err := json.Marshal(res)
	if err != nil {
		panic(err)
	}
	if err = os.WriteFile("/gitedge/result.json", raw, 0600); err != nil {
		panic(err)
	}
	if res.Status == "failure" {
		os.Exit(1)
	}
}
