/* screen-profile.jsx — intake form: who you are / what matters. */

function WSlider({ label, value, onChange, hint, help }) {
  return (
    <div>
      <div className="slider-head">
        <span>{label}{help && <InfoTip text={help} label={`About ${label}`} />}</span>
        <span className="val">{Math.round(value)}/10</span>
      </div>
      <input type="range" min="0" max="10" step="0.1" value={value} style={{ "--p": `${value * 10}%` }}
      aria-label={`${label} importance, 0 to 10`}
      onChange={(e) => onChange(Number(e.target.value))} />
    </div>);

}

function evenSplit(n) {return Array.from({ length: n }, () => Math.round(100 / n));}

function PracticeStates({ value, onChange }) {
  const addRow = () => {
    const weights = evenSplit(value.length + 1);
    onChange([...value, { state: "", weight: 0 }].map((r, i) => ({ ...r, weight: weights[i] })));
  };
  const update = (i, patch) => onChange(value.map((r, j) => j === i ? { ...r, ...patch } : r));
  const remove = (i) => onChange(value.filter((_, j) => j !== i));
  return (
    <div className="field" style={{ marginTop: 18 }}>
      <label>Where you want to practice {value.length > 1 && "(weight %)"}</label>
      {value.map((row, i) =>
      <div className="weighted-row" key={i}>
          <select value={row.state} aria-label={`Practice state ${i + 1}`}
            onChange={(e) => update(i, { state: e.target.value })}>
            <option value="">Select state</option>
            {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {value.length > 1 &&
        <input type="number" min="0" value={row.weight}
        onChange={(e) => update(i, { weight: Number(e.target.value) })} />
        }
          {value.length > 1 &&
        <button type="button" className="btn xs ghost" onClick={() => remove(i)}
        aria-label="Remove state">×</button>
        }
        </div>
      )}
      <div><button type="button" className="btn sm ghost" onClick={addRow}>+ Add a second market</button></div>
    </div>);

}

function InstateList({ value, onChange }) {
  const add = () => onChange([...value, ""]);
  const update = (i, v) => onChange(value.map((s, j) => j === i ? v : s));
  const remove = (i) => onChange(value.filter((_, j) => j !== i));
  return (
    <div className="field" style={{ marginTop: 0 }}>
      <label>In-state tuition eligibility
        <InfoTip text="States where you qualify as a resident. Public schools there are priced at resident tuition." />
      </label>
      {value.map((st, i) =>
      <div className="weighted-row" key={i}>
          <select value={st} aria-label={`In-state tuition state ${i + 1}`}
            onChange={(e) => update(i, e.target.value)}>
            <option value="">Select state</option>
            {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {value.length > 1 &&
        <button type="button" className="btn xs ghost" onClick={() => remove(i)}
        aria-label="Remove state">×</button>
        }
        </div>
      )}
      <div><button type="button" className="btn sm ghost" onClick={add}>+ Add state</button></div>
    </div>);

}

function FinancialsSection({ form, set }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ marginTop: 22 }}>
      <button type="button" className="fin-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span>{open ? "▾" : "▸"}</span> Financials
        <span className="optional-badge">Optional</span>
      </button>
      {open &&
      <div className="fin-body">
          <div className="field">
            <label>Household income ($)</label>
            <input type="number" min="0" step="1000" value={form.income} placeholder="0"
          onChange={(e) => set("income", e.target.value)} />
          </div>
          <div className="field-grid" style={{ marginTop: 14 }}>
            <div className="field">
              <label>Savings for law school ($)</label>
              <input type="number" min="0" step="1000" value={form.cash} placeholder="0"
            onChange={(e) => set("cash", e.target.value)} />
            </div>
            <div className="field">
              <label>Existing student debt ($)</label>
              <input type="number" min="0" step="1000" value={form.debt} placeholder="0"
            onChange={(e) => set("debt", e.target.value)} />
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <InstateList value={form.instate} onChange={(v) => set("instate", v)} />
          </div>
        </div>
      }
    </div>);

}

function ProfileScreen({ form, setForm, onSubmit, loading }) {
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const loadScenario = (f) => setForm(f);
  const lsatOk = form.noLsat || (Number(form.lsat) >= 120 && Number(form.lsat) <= 180);
  const gpaOk = Number(form.gpa) > 0 && Number(form.gpa) <= 4.33;
  return (
    <div>
      <div className="intake-head">
        <h1 className="display">Where should you go to law school<span className="colon">:</span></h1>
        <p>Tell us a little about yourself. We'll rank every ABA-accredited school by how realistic it is, how well it serves your career, and what it would really cost

          <em> you</em>.</p>
      </div>

      <div className="intake-grid">
        <section>
          <h2>Who you are</h2>
          <p className="sec-sub"></p>

          <div className="field-grid">
            <div className="field">
              <label>LSAT</label>
              <input type="number" min="120" max="180" value={form.lsat} disabled={form.noLsat}
              placeholder="120–180" onChange={(e) => set("lsat", e.target.value)} />
              <div className="checkbox-row" style={{ fontSize: 12.5, marginTop: 2 }}>
                <input id="nolsat" type="checkbox" checked={form.noLsat}
                onChange={(e) => set("noLsat", e.target.checked)} />
                <label htmlFor="nolsat">I haven't taken it yet</label>
              </div>
            </div>
            <div className="field">
              <label>Undergrad GPA</label>
              <input type="number" min="0" max="4" step="0.01" value={form.gpa}
              placeholder="0.00–4.00" onChange={(e) => set("gpa", e.target.value)} />
            </div>
          </div>

          <div className="field" style={{ marginTop: 18 }}>
            <label>Career goal</label>
            <select value={form.goal} aria-label="Career goal" onChange={(e) => set("goal", e.target.value)}>
              {GOALS.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>

          <PracticeStates value={form.practice} onChange={(v) => set("practice", v)} />
          <FinancialsSection form={form} set={set} />
        </section>

        <section>
          <h2>What matters to you</h2>
          <p className="sec-sub">These set the weights in your ranking.</p>
          <div className="weights">
            <WSlider label="Career fit" value={form.careerW} onChange={(v) => set("careerW", v)}
            hint="placement into your goal, employment, bar passage" />
            <WSlider label="Location fit" value={form.locW} onChange={(v) => set("locW", v)}
            hint="how strongly the school feeds your market" />
            <WSlider label="Cost sensitivity" value={form.costW} onChange={(v) => set("costW", v)}
            help="Weights net cost and scholarship odds more heavily in your ranking. Lower it if prestige or outcomes matter more than price."
            hint="net debt + scholarship odds" />
          </div>

          <div className="checkbox-row" style={{ marginTop: 26 }}>
            <input id="transfer" type="checkbox" checked={form.transfer}
            onChange={(e) => set("transfer", e.target.checked)} />
            <label htmlFor="transfer">I'd consider transferring up after 1L</label>
          </div>

          <div className="intake-actions">
            <button className="btn primary" style={{ width: "100%" }} disabled={loading || !lsatOk || !gpaOk}
            title={!lsatOk ? "Enter an LSAT (120–180) or check “I haven't taken it yet”" : !gpaOk ? "Enter a GPA (0–4.33)" : undefined}
            onClick={onSubmit}>{loading ? "Matching…" : "Find my schools →"}</button>
          </div>

          <ScenariosPanel form={form} onLoad={loadScenario} />
        </section>
      </div>
    </div>);

}

window.ProfileScreen = ProfileScreen;
