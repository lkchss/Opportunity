/* app.jsx — app shell: routing, state, API calls.
   Scoring happens on the backend: POST /api/match per submitted profile (and
   per what-if LSAT bump); GET /api/schools feeds the raw rankings browser. */

const DEFAULT_FORM = {
  lsat: "", noLsat: false, gpa: "", goal: "Unsure",
  practice: [{ state: "", weight: 100 }], instate: [""],
  income: "", cash: "", debt: "",
  careerW: 5, locW: 5, costW: 5, transfer: false
};

const STORE_KEY = "oplaw-v2-profile";

/* Coerce an untrusted form (share link, old localStorage) back to a safe shape. */
function normalizeForm(f) {
  const out = { ...DEFAULT_FORM, ...f };
  if (!GOALS.includes(out.goal)) out.goal = "Unsure";
  if (!Array.isArray(out.practice) || !out.practice.length ||
      out.practice.some((p) => typeof p !== "object" || p == null)) {
    out.practice = [{ state: "", weight: 100 }];
  }
  if (!Array.isArray(out.instate) || !out.instate.length) out.instate = [""];
  ["careerW", "locW", "costW"].forEach((k) => {
    const n = Number(out[k]);
    out[k] = Number.isNaN(n) ? DEFAULT_FORM[k] : Math.max(0, Math.min(10, n));
  });
  return out;
}

function loadStoredForm() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return normalizeForm(JSON.parse(raw));
  } catch (e) {/* ignore */}
  return DEFAULT_FORM;
}

/* The submitted form snapshot, viewed the way the screens expect it. */
function profileView(f) {
  return { ...f, lsat: f.noLsat ? null : Number(f.lsat), gpa: Number(f.gpa) };
}

async function fetchMatch(formSnapshot, lsatOverride, weightsOverride, applyOpts) {
  const res = await fetch("/api/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildPayload(formSnapshot, lsatOverride, weightsOverride, applyOpts)),
  });
  // Error bodies aren't always JSON (Basic-Auth 401, proxy 502) — don't let
  // the parse failure mask the real status.
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `Matching failed (${res.status}).`);
  return adaptMatchResponse(json, formSnapshot.goal || "Unsure");
}

function App() {
  const [screen, setScreen] = React.useState("intake");
  const [form, setForm] = React.useState(loadStoredForm);
  const [submitted, setSubmitted] = React.useState(null); // form snapshot at submit
  const [data, setData] = React.useState(null);           // { schools, plan }
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [whatIf, setWhatIf] = React.useState({ delta: 0, data: null });
  const [compareIds, setCompareIds] = React.useState([]);
  const [openedId, setOpenedId] = React.useState(null);
  const [rview, setRview] = React.useState("guided");
  const [modal, setModal] = React.useState(null);
  const [rawSchools, setRawSchools] = React.useState(null); // adapted /api/schools | "error"
  // TweaksPanel: per-score weight multipliers. null = defaults (key omitted from payload).
  const [tweakWeights, setTweakWeights] = React.useState(null);
  const [tweakOpen, setTweakOpen] = React.useState(false);
  // Apply-plan controls: risk posture + opt-in long shots. Mirrored in a ref so
  // async weight/what-if fetches include the current options too.
  const [applyStrategy, setApplyStrategy] = React.useState("balanced");
  const [includeHard, setIncludeHard] = React.useState(false);
  const applyRef = React.useRef({ strategy: "balanced", includeHard: false });
  // Bumped on every successful submit so in-flight what-if responses from an
  // older profile can be recognized as stale and dropped.
  const submitSeq = React.useRef(0);

  const submit = async (f = form) => {
    setLoading(true);
    setError(null);
    try {
      // Reset tweaks on a full profile submit so the results reflect the profile, not stale weights.
      setTweakWeights(null);
      // Reset apply-plan controls to defaults for the new profile.
      applyRef.current = { strategy: "balanced", includeHard: false };
      setApplyStrategy("balanced");
      setIncludeHard(false);
      const adapted = await fetchMatch(f, undefined, null, applyRef.current);
      submitSeq.current += 1;
      setData(adapted);
      setSubmitted(f);
      setWhatIf({ delta: 0, data: null });
      setCompareIds([]);
      setScreen("results");
      track("match_run");
      try {localStorage.setItem(STORE_KEY, JSON.stringify(f));} catch (e) {/* ignore */}
      // Shareable link: profile lives in the URL hash, restored on load.
      try {window.history.replaceState(null, "", "#p=" + encodeShare(f));} catch (e) {/* ignore */}
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // Re-rank with new weights (called by TweaksPanel after debounce).
  // Uses the same submitted form snapshot; weight changes go through fetchMatch
  // so what-if/pure-fit/transfer tabs stay consistent.
  const resubmitWithWeights = React.useCallback(async (w) => {
    if (!submitted) return;
    if (w) track("weights_changed");
    setTweakWeights(w);
    const seq = submitSeq.current;
    try {
      const adapted = await fetchMatch(submitted, undefined, w, applyRef.current);
      // Drop if the user re-submitted the profile while this was in flight.
      if (seq === submitSeq.current) {
        setData(adapted);
        setWhatIf({ delta: 0, data: null });
      }
    } catch (e) {/* keep the last good result — don't show an error for a tweak failure */}
  }, [submitted]);

  // Re-build the apply plan when the user changes risk posture or toggles long
  // shots. Re-fetches (like weights) so the slate stays a single backend truth.
  const updateApplyPlan = React.useCallback(async (next) => {
    if (!submitted) return;
    applyRef.current = { ...applyRef.current, ...next };
    if (next.strategy !== undefined) {setApplyStrategy(next.strategy);track("apply_strategy_changed", next.strategy);}
    if (next.includeHard !== undefined) {setIncludeHard(next.includeHard);track("apply_longshots_toggled", next.includeHard ? "on" : "off");}
    const seq = submitSeq.current;
    try {
      const adapted = await fetchMatch(submitted, undefined, tweakWeights, applyRef.current);
      if (seq === submitSeq.current) {
        setData(adapted);
        setWhatIf({ delta: 0, data: null });
      }
    } catch (e) {/* keep the last good slate on a transient failure */}
  }, [submitted, tweakWeights]);

  // Opened via a share link: restore the profile and run the match once.
  React.useEffect(() => {
    const m = window.location.hash.match(/^#p=(.+)$/);
    if (!m) return;
    try {
      const f = normalizeForm(decodeShare(m[1]));
      setForm(f);
      submit(f);
    } catch (e) {/* malformed share link — start fresh */}
  }, []);

  /* What-if: each LSAT bump re-runs the match server-side and re-tiers live.
     Stale responses are dropped if the user keeps clicking. */
  const setWhatIfDelta = async (d) => {
    if (!submitted || submitted.noLsat) return;
    if (d <= 0) {setWhatIf({ delta: 0, data: null });return;}
    track("whatif_used");
    const seq = submitSeq.current;
    setWhatIf((w) => ({ ...w, delta: d }));
    try {
      // Pass current tweakWeights so what-if respects the user's weight adjustments.
      const adapted = await fetchMatch(submitted, Number(submitted.lsat) + d, tweakWeights, applyRef.current);
      // Drop if the user kept clicking (delta moved on) or re-submitted the
      // profile while this request was in flight.
      setWhatIf((w) => w.delta === d && seq === submitSeq.current ? { delta: d, data: adapted } : w);
    } catch (e) {/* keep the last good payload */}
  };

  const nav = (where) => {
    if (where === "methodology") {track("methodology_opened");setModal("how");return;}
    if (where === "home") {setScreen("intake");} else
    if (where === "matches") {setScreen(data ? "results" : "intake");} else
    if (where === "rankings") {
      track("rankings_opened");
      setScreen("rankings");
      if (!rawSchools || rawSchools === "error") {
        setRawSchools(null);
        fetch("/api/schools")
          .then((r) => r.json())
          .then((j) => setRawSchools((j.schools || []).map(adaptRaw)))
          .catch(() => setRawSchools("error"));
      }
    }
    window.scrollTo({ top: 0 });
  };

  const openSchool = (m) => {track("school_opened");setOpenedId(m.id);setScreen("detail");window.scrollTo({ top: 0 });};
  const toggleCompare = (id) =>
  setCompareIds((ids) => ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);

  const eff = whatIf.delta > 0 && whatIf.data ? whatIf.data : data;
  const results = eff ? eff.schools : null;
  const profile = submitted ? profileView(submitted) : null;
  const opened = results && openedId ? results.find((m) => m.id === openedId) : null;
  const compareSchools = results ? results.filter((m) => compareIds.includes(m.id)) : [];

  const mastView = screen === "rankings" ? "rankings" :
  screen === "results" || screen === "detail" || screen === "compare" ? "matches" : "";

  return (
    <div className="shell">
      <Masthead view={mastView} onNav={nav} />

      <main>
      {error && <div className="error-banner">{error}</div>}
      {loading && <div className="center-msg"><div className="spinner" />Matching schools…</div>}

      {!loading && screen === "intake" &&
      <ProfileScreen form={form} setForm={setForm} onSubmit={() => submit()} loading={loading} />
      }
      {!loading && screen === "results" && results && profile &&
      <ResultsScreen results={results} plan={eff.plan} portfolio={eff ? eff.portfolio : null} profile={profile}
      whatIf={whatIf.delta} setWhatIf={setWhatIfDelta}
      onOpen={openSchool} onEditProfile={() => setScreen("intake")}
      compareIds={compareIds} onToggleCompare={toggleCompare}
      onClearCompare={() => setCompareIds([])}
      rview={rview} setRview={setRview}
      onCompare={() => {track("compare_opened");setScreen("compare");window.scrollTo({ top: 0 });}}
      tweakOpen={tweakOpen} onTweakToggle={() => setTweakOpen((v) => {const next = !v;if (next) track("weights_opened");return next;})}
      applyStrategy={applyStrategy} includeHard={includeHard} onApplyChange={updateApplyPlan} />
      }

      <ScoreWeightsPanel
        open={tweakOpen}
        onClose={() => setTweakOpen(false)}
        onWeightsChange={resubmitWithWeights}
      />
      {!loading && screen === "detail" && opened && profile &&
      <DetailScreen m={opened} profile={profile}
      onBack={() => {setScreen("results");}} />
      }
      {!loading && screen === "compare" && results &&
      <CompareScreen schools={compareSchools} profile={profile}
      onBack={() => setScreen("results")} onRemove={toggleCompare} />
      }
      {!loading && screen === "rankings" &&
      <RankingsScreen schools={rawSchools === "error" ? null : rawSchools}
      error={rawSchools === "error"} onRetry={() => nav("rankings")} />
      }
      </main>

      <footer className="footer-note">
        <span className="mono">Your profile is never saved — only anonymous feature-usage counts.
        </span>
        <span className="mono">
          <button type="button" className="linklike" onClick={() => {track("report_opened");setModal("report");}}>
            Report a bug / request a feature</button>
        </span>
      </footer>

      {modal === "how" && <Methodology onClose={() => setModal(null)} />}
      {modal === "report" && <ReportForm onClose={() => setModal(null)} />}
    </div>);

}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
