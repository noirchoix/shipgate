<script lang="ts">
  import { api, type AuditResponse, type Finding, type Health, type RepoFile, type SkillCard, type UploadedRepository } from '$lib/api/client';

  type Stage = 'intake' | 'scope' | 'audit' | 'launch';

  let stage = $state<Stage>('intake');
  let health = $state<Health | null>(null);
  let skills = $state<SkillCard[]>([]);
  let upload = $state<UploadedRepository | null>(null);
  let files = $state<RepoFile[]>([]);
  let selected = $state<string[]>([]);
  let filter = $state('');
  let deploymentTarget = $state('auto');
  let useLlm = $state(true);
  let objective = $state('Assess this repository for launch readiness. Prioritize environment variables, build commands, API base URLs, CORS, deployment config, security exposure, rollback and smoke-test gaps.');
  let result = $state<AuditResponse | null>(null);
  let loading = $state(false);
  let error = $state('');
  let copied = $state('');

  const visibleFiles = $derived(files.filter((file) => {
    const q = filter.toLowerCase();
    return !q || `${file.path} ${file.kind}`.toLowerCase().includes(q);
  }));

  const counts = $derived({
    blocker: result?.findings.filter((f) => f.severity === 'blocker').length ?? 0,
    warning: result?.findings.filter((f) => f.severity === 'warning').length ?? 0,
    suggestion: result?.findings.filter((f) => f.severity === 'suggestion').length ?? 0,
    nit: result?.findings.filter((f) => f.severity === 'nit').length ?? 0,
    pass: result?.findings.filter((f) => f.severity === 'pass').length ?? 0
  });

  async function uploadRepo(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    loading = true;
    error = '';
    try {
      upload = await api.upload(file);
      const list = await api.files(upload.session_id);
      files = list.files;
      selected = list.default_targets;
      stage = 'scope';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      loading = false;
    }
  }

  function toggleFile(path: string) {
    selected = selected.includes(path) ? selected.filter((x) => x !== path) : [...selected, path];
  }

  async function runAudit() {
    if (!upload) return;
    loading = true;
    error = '';
    stage = 'audit';
    try {
      result = await api.audit({ session_id: upload.session_id, objective, target_files: selected, deployment_target: deploymentTarget, use_llm: useLlm });
      stage = 'launch';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Audit failed';
      stage = 'scope';
    } finally {
      loading = false;
    }
  }

  async function copyText(label: string, text: string) {
    await navigator.clipboard.writeText(text);
    copied = label;
    setTimeout(() => copied = '', 1300);
  }

  function severityLabel(severity: Finding['severity']) {
    if (severity === 'blocker') return 'Blocker';
    if (severity === 'warning') return 'Warning';
    if (severity === 'suggestion') return 'Suggestion';
    if (severity === 'nit') return 'Nit';
    return 'Pass';
  }

  $effect(() => {
    api.health().then((data) => health = data).catch(() => {});
    api.skills().then((data) => skills = data).catch(() => {});
  });
</script>

<svelte:head><title>ShipGate Launch Auditor</title></svelte:head>

<main class="shipgate-shell">
  <aside class="sidecar">
    <div class="brand">
      <div class="brand-mark">SG</div>
      <div><strong>ShipGate</strong><span>Launch Auditor</span></div>
    </div>

    <nav aria-label="Audit stages">
      <button type="button" class:active={stage === 'intake'} onclick={() => stage = 'intake'}>01 Intake</button>
      <button type="button" class:active={stage === 'scope'} disabled={!upload} onclick={() => stage = 'scope'}>02 Scope</button>
      <button type="button" class:active={stage === 'audit'} disabled={!upload} onclick={() => stage = 'audit'}>03 Audit</button>
      <button type="button" class:active={stage === 'launch'} disabled={!result} onclick={() => stage = 'launch'}>04 Launch Plan</button>
    </nav>

    <section class="signal-card">
      <span class:online={health?.ai_enabled}></span>
      <div><strong>{health?.ai_enabled ? 'LLM synthesis online' : 'Static audit mode'}</strong><p>{health?.provider ?? 'offline'} · {health?.audits ?? 0} stored audits</p></div>
    </section>

    <section class="agents">
      <h2>Auditors</h2>
      {#each skills.slice(0, 7) as skill}
        <article><strong>{skill.name}</strong><p>{skill.incorporated_as}</p></article>
      {/each}
    </section>
  </aside>

  <section class="workspace">
    <header class="hero">
      <div>
        <p class="eyebrow">Operations readiness cockpit</p>
        <h1>Audit a repository before it ships.</h1>
        <p class="subhead">Upload a project ZIP. ShipGate checks environment contracts, build commands, deployment posture, security exposure, smoke tests and rollback readiness.</p>
      </div>
      {#if upload}
        <button type="button" class="primary" onclick={runAudit} disabled={loading || !selected.length}>{loading ? 'Auditing…' : 'Run launch audit'}</button>
      {/if}
    </header>

    {#if error}<p class="error">{error}</p>{/if}

    {#if stage === 'intake'}
      <section class="intake-grid">
        <article class="upload-panel">
          <div class="panel-label">Repository package</div>
          <label for="repo-upload">Upload GitHub ZIP</label>
          <input id="repo-upload" type="file" accept=".zip" onchange={uploadRepo} />
          <p>Defaults target README, .env.example, package/requirements files, SvelteKit/FastAPI configs, Docker/Vercel/Render/Railway files and GitHub Actions.</p>
        </article>

        <article class="launch-visual" aria-hidden="true">
          <svg viewBox="0 0 720 460">
            <defs>
              <linearGradient id="gateFill" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fafff8"/><stop offset="100%" stop-color="#e5f1e8"/></linearGradient>
            </defs>
            <rect class="backdrop" x="52" y="38" width="616" height="384" rx="36"/>
            <rect class="terminal" x="102" y="86" width="256" height="238" rx="22"/>
            <circle class="dot red" cx="132" cy="118" r="6"/><circle class="dot amber" cx="154" cy="118" r="6"/><circle class="dot green" cx="176" cy="118" r="6"/>
            <path class="line" d="M132 166h116M132 198h170M132 230h132M132 262h190"/>
            <rect class="gate" x="412" y="104" width="172" height="220" rx="24"/>
            <path class="gate-path" d="M456 274V158h86v116"/>
            <path class="rocket" d="M498 124c38 24 58 58 60 104-46-2-80-22-104-60 11-21 23-33 44-44z"/>
            <path class="flame" d="M448 178c-18 8-30 22-36 42 20-6 34-18 42-36"/>
            <circle class="check-bg" cx="560" cy="318" r="36"/>
            <path class="check" d="M544 319l12 12 25-30"/>
            <path class="route" d="M362 210h44"/><path class="route-head" d="M392 194l20 16-20 16"/>
          </svg>
        </article>
      </section>
    {/if}

    {#if stage === 'scope' && upload}
      <section class="scope-grid">
        <article class="panel files-panel">
          <div class="panel-head">
            <div><h2>{upload.repo_name}</h2><p>{upload.file_count} files · {upload.detected_stack.join(' · ')}</p></div>
            <input aria-label="Filter files" placeholder="Filter files" bind:value={filter} />
          </div>
          <div class="file-list">
            {#each visibleFiles as file}
              <button type="button" class:selected={selected.includes(file.path)} onclick={() => toggleFile(file.path)}>
                <span>{file.path}</span><small>{file.kind} · {(file.size / 1024).toFixed(1)} KB</small>
              </button>
            {/each}
          </div>
        </article>

        <aside class="panel launch-config">
          <h2>Launch target</h2>
          <label for="deployment-target">Deployment target</label>
          <select id="deployment-target" bind:value={deploymentTarget}>
            <option value="auto">Auto-detect</option>
            <option value="Vercel + API host">Vercel frontend + API host</option>
            <option value="Render">Render</option>
            <option value="Railway">Railway</option>
            <option value="Docker">Docker</option>
            <option value="Manual">Manual</option>
          </select>
          <label for="objective">Audit objective</label>
          <textarea id="objective" bind:value={objective}></textarea>
          <label class="check-row" for="llm"><input id="llm" type="checkbox" bind:checked={useLlm}/><span>Use LLM synthesis when configured</span></label>
          <button class="primary wide" type="button" onclick={runAudit} disabled={!selected.length || loading}>Audit {selected.length} selected files</button>
        </aside>
      </section>
    {/if}

    {#if stage === 'audit'}
      <section class="audit-running">
        <div class="scanner"></div>
        <h2>ShipGate is running launch gates</h2>
        <p>Checking env templates, build scripts, API runtime, deployment files, CORS, secrets, documentation and rollback evidence.</p>
      </section>
    {/if}

    {#if stage === 'launch' && result}
      <section class="launch-grid">
        <div class="main-report">
          <section class={`readiness-card ${result.readiness}`}>
            <span>Launch score</span><strong>{result.score}</strong><p>{result.summary}</p>
          </section>
          <section class="count-grid">
            <div><strong>{counts.blocker}</strong><span>Blockers</span></div>
            <div><strong>{counts.warning}</strong><span>Warnings</span></div>
            <div><strong>{counts.suggestion}</strong><span>Suggestions</span></div>
            <div><strong>{counts.pass}</strong><span>Passed</span></div>
          </section>

          <section class="panel findings">
            <h2>Launch findings</h2>
            {#each result.findings as finding}
              <article class={`finding ${finding.severity}`}>
                <div class="finding-top"><span>{severityLabel(finding.severity)}</span><small>{finding.agent}</small></div>
                <h3>{finding.title}</h3>
                {#if finding.file}<p class="file-ref">{finding.file}</p>{/if}
                <p>{finding.evidence}</p>
                <div class="split"><strong>Why</strong><span>{finding.why_it_matters}</span></div>
                <div class="split"><strong>Action</strong><span>{finding.recommendation}</span></div>
                {#if finding.command}<pre>{finding.command}</pre>{/if}
              </article>
            {/each}
          </section>
        </div>

        <aside class="side-report">
          <section class="panel">
            <div class="side-head"><h2>Predeploy checklist</h2><button type="button" onclick={() => copyText('pre', result.launch_plan.predeploy_checklist.join('\n'))}>{copied === 'pre' ? 'Copied' : 'Copy'}</button></div>
            <ol>{#each result.launch_plan.predeploy_checklist as item}<li>{item}</li>{/each}</ol>
          </section>
          <section class="panel">
            <h2>Environment matrix</h2>
            <div class="env-list">{#each result.launch_plan.environment_matrix.slice(0, 12) as env}<div><strong>{env.name}</strong><span>{env.exposure} · {env.source}</span></div>{/each}</div>
          </section>
          <section class="panel">
            <h2>Smoke tests</h2>
            {#each result.launch_plan.smoke_tests as cmd}<pre>{cmd.command}</pre><p>{cmd.purpose}</p>{/each}
          </section>
          <section class="panel">
            <div class="side-head"><h2>Markdown report</h2><button type="button" onclick={() => copyText('report', result.markdown_report)}>{copied === 'report' ? 'Copied' : 'Copy'}</button></div>
            <pre class="report-pre">{result.markdown_report}</pre>
          </section>
        </aside>
      </section>
    {/if}
  </section>
</main>

<style>
  :global(body){margin:0;background:#f6f7f2;color:#18211d;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:14px}.shipgate-shell{min-height:100vh;display:grid;grid-template-columns:260px minmax(0,1fr)}.sidecar{background:#10201a;color:#f8fff8;padding:22px 18px;display:flex;flex-direction:column;gap:22px;position:sticky;top:0;height:100vh;box-sizing:border-box}.brand{display:flex;gap:12px;align-items:center}.brand-mark{width:38px;height:38px;border-radius:14px;background:#d8f2bf;color:#10201a;display:grid;place-items:center;font-weight:800}.brand strong{display:block;font-size:15px}.brand span,.signal-card p{display:block;color:#b9c9bd;font-size:12px}nav{display:grid;gap:8px}nav button{text-align:left;border:0;background:transparent;color:#aab9ae;border-radius:13px;padding:10px 12px;cursor:pointer}nav button.active,nav button:hover{background:#1d342b;color:#fff}nav button:disabled{opacity:.35}.signal-card,.agents{border:1px solid #2d4439;background:#172b23;border-radius:20px;padding:14px}.signal-card{display:flex;gap:10px}.signal-card>span{width:9px;height:9px;border-radius:50%;background:#78887e;margin-top:4px}.signal-card>span.online{background:#7ce0a0}.signal-card strong{font-size:13px}.agents{margin-top:auto;max-height:340px;overflow:auto}.agents h2{font-size:11px;text-transform:uppercase;letter-spacing:.16em;color:#d8f2bf;margin:0 0 10px}.agents article{border-top:1px solid #2d4439;padding:10px 0}.agents article strong{font-size:12px}.agents article p{margin:2px 0 0;color:#b9c9bd;font-size:11px}.workspace{padding:28px 32px 42px}.hero{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:22px}.eyebrow{margin:0 0 8px;color:#477057;text-transform:uppercase;letter-spacing:.14em;font-size:11px}.hero h1{margin:0;font-size:36px;line-height:1;letter-spacing:-.055em}.subhead{max-width:840px;color:#53645b;line-height:1.55;margin:12px 0 0}.primary,button{border:0;border-radius:999px;background:#16382b;color:white;padding:10px 15px;cursor:pointer;font-size:13px}.primary:hover{background:#0f2a20}button:disabled{opacity:.45;cursor:not-allowed}.error{background:#fff0e8;border:1px solid #ecc7b4;color:#8c331f;padding:11px 13px;border-radius:16px}.intake-grid,.scope-grid,.launch-grid{display:grid;grid-template-columns:minmax(360px,.72fr) minmax(0,1.28fr);gap:18px}.upload-panel,.panel,.readiness-card,.audit-running{background:#fffdfa;border:1px solid #dce4d8;border-radius:26px;padding:20px;box-shadow:0 24px 80px rgba(26,55,39,.06)}.panel-label{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:#477057;margin-bottom:14px}label{display:block;font-size:12px;color:#53645b;margin:0 0 8px}input,textarea,select{box-sizing:border-box;width:100%;border:1px solid #d1ddd2;background:#fff;border-radius:15px;padding:11px 12px;font:inherit;color:#18211d}input[type=file]{padding:14px}textarea{min-height:140px;resize:vertical;line-height:1.5}.upload-panel p,.audit-running p,.side-report p{color:#53645b;line-height:1.55}.launch-visual{display:grid;place-items:center;border-radius:26px;background:#eaf2e7;border:1px solid #d6e3d3}.launch-visual svg{width:min(640px,96%)}.launch-visual .backdrop{fill:url(#gateFill);stroke:#cbdcc8}.terminal,.gate{fill:#fffdfa;stroke:#16382b;stroke-width:3}.line,.gate-path,.rocket,.flame,.check,.route,.route-head{fill:none;stroke:#16382b;stroke-width:5;stroke-linecap:round;stroke-linejoin:round}.rocket{fill:#d8f2bf}.check-bg{fill:#d8f2bf;stroke:#16382b;stroke-width:4}.dot.red{fill:#ed7b68}.dot.amber{fill:#f3c969}.dot.green{fill:#69c98f}.scope-grid{grid-template-columns:minmax(0,1fr) 420px}.panel-head{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:14px}.panel-head h2,.launch-config h2,.findings h2,.side-head h2,.side-report h2{margin:0;font-size:16px}.panel-head p{margin:3px 0 0;color:#69786f;font-size:12px}.panel-head input{max-width:260px}.file-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:9px;max-height:65vh;overflow:auto}.file-list button{text-align:left;background:#f8fbf4;color:#18211d;border:1px solid #dce6d7;border-radius:15px;padding:11px}.file-list button.selected{background:#16382b;color:white;border-color:#16382b}.file-list span{display:block;font-size:12px;overflow:hidden;text-overflow:ellipsis}.file-list small{display:block;color:#68796f;font-size:11px;margin-top:5px}.file-list button.selected small{color:#c6d7ca}.check-row{display:flex;gap:9px;align-items:center;margin:16px 0}.check-row input{width:auto}.wide{width:100%}.audit-running{text-align:center;padding:64px}.scanner{width:58px;height:58px;margin:0 auto 18px;border:4px solid #d8f2bf;border-top-color:#16382b;border-radius:50%;animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}.launch-grid{grid-template-columns:minmax(0,1fr) 430px}.main-report{display:grid;gap:14px}.readiness-card span{text-transform:uppercase;letter-spacing:.14em;font-size:11px;color:#477057}.readiness-card strong{display:block;font-size:58px;letter-spacing:-.06em}.readiness-card p{color:#53645b;line-height:1.5}.readiness-card.blocked{border-color:#ebb5a8;background:#fff7f4}.readiness-card.caution{border-color:#ebd38d;background:#fffaf0}.readiness-card.ready{border-color:#bedfb2;background:#f8fff4}.count-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.count-grid div{background:#fffdfa;border:1px solid #dce4d8;border-radius:18px;padding:14px}.count-grid strong{font-size:25px;display:block}.count-grid span{font-size:12px;color:#69786f}.finding{border:1px solid #dce4d8;border-radius:18px;padding:14px;margin-top:10px;background:#fff}.finding.blocker{border-color:#ebb5a8;background:#fff7f4}.finding.warning{border-color:#ebd38d;background:#fffaf0}.finding.suggestion{border-color:#cbdcc8;background:#f8fbf4}.finding.pass{border-color:#bedfb2;background:#f8fff4}.finding-top{display:flex;justify-content:space-between}.finding-top span{text-transform:uppercase;letter-spacing:.13em;font-size:11px;color:#477057}.finding h3{font-size:15px;margin:9px 0}.finding p,.split span,.side-report li{font-size:12px;color:#53645b;line-height:1.5}.file-ref{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#2f6646!important}.split{display:grid;grid-template-columns:58px 1fr;gap:10px;border-top:1px solid #e9eee6;padding-top:9px;margin-top:9px}.side-report{display:grid;gap:14px;align-self:start}.side-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.side-head button{background:#fff;color:#18211d;border:1px solid #d1ddd2;padding:7px 11px;font-size:12px}.env-list{display:grid;gap:8px}.env-list div{background:#f8fbf4;border:1px solid #e2eadf;border-radius:14px;padding:9px}.env-list strong{display:block;font-size:12px}.env-list span{font-size:11px;color:#69786f}pre{max-height:340px;overflow:auto;background:#10201a;color:#ecfff0;border-radius:16px;padding:12px;font-size:11px;line-height:1.45}.report-pre{max-height:420px}@media(max-width:1120px){.shipgate-shell{grid-template-columns:1fr}.sidecar{position:static;height:auto}.intake-grid,.scope-grid,.launch-grid{grid-template-columns:1fr}.hero{display:grid}.count-grid{grid-template-columns:repeat(2,1fr)}}
</style>
